"""Translate pending fields: human overrides first, then AI with glossary."""

import argparse
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import ai_client
from translation_store import (
    load_json,
    load_list,
    load_translations,
    save_json,
    set_translation,
)


def _human_get(human: dict, unique_name: str, field: str) -> str | None:
    entry = human.get(unique_name)
    if isinstance(entry, dict):
        value = entry.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _call_with_retries(ai_translate, en_text: str, glossary: dict, max_retries: int,
                       backoff_s: float, sleep) -> str:
    last_error = None
    for attempt in range(max_retries):
        try:
            return ai_translate(en_text, glossary)
        except ai_client.AIError as e:
            last_error = e
            sleep(backoff_s * (2 ** attempt))
    raise ai_client.AIError(f"failed after {max_retries} retries: {last_error}")


class ConsecutiveFailureError(Exception):
    """Raised when AI translation keeps failing — the API is likely down."""


def _translate_sequential(pending: list[dict], translations: dict, human: dict, glossary: dict,
                          ai_translate, *, at: str, max_retries: int, backoff_s: float,
                          sleep, max_consecutive_failures: int) -> tuple[int, list[str]]:
    translated = 0
    failures = []
    consecutive_failures = 0
    for item in pending:
        unique_name, field, en_text = item["unique_name"], item["field"], item["en"]
        human_zh = _human_get(human, unique_name, field)
        if human_zh is not None:
            set_translation(translations, unique_name, field, en_text, human_zh, at)
            translated += 1
            consecutive_failures = 0
            continue
        try:
            zh = _call_with_retries(ai_translate, en_text, glossary, max_retries, backoff_s, sleep)
        except ai_client.AIError as e:
            consecutive_failures += 1
            failures.append(f"{unique_name}.{field}: {e}")
            if consecutive_failures >= max_consecutive_failures:
                raise ConsecutiveFailureError(
                    f"连续 {max_consecutive_failures} 次 AI 翻译失败,API 可能不可用,已中止\n"
                    + "\n".join(f"  FAIL {f}" for f in failures[-3:])
                ) from e
            continue
        set_translation(translations, unique_name, field, en_text, zh, at)
        translated += 1
        consecutive_failures = 0
    return translated, failures


def translate_pending(pending: list[dict], translations: dict, human: dict, glossary: dict,
                      ai_translate, *, at: str, max_retries: int = 3, backoff_s: float = 2.0,
                      sleep=time.sleep, max_consecutive_failures: int = 5,
                      max_workers: int = 1,
                      abort_failure_threshold: int = 25) -> tuple[int, list[str]]:
    """Translate each pending item. Returns (translated_count, failure_messages).

    Failed items are left untranslated (English kept) and reported, not fatal.
    max_workers=1(默认): 顺序执行,连续 max_consecutive_failures 次 AI 失败
    抛 ConsecutiveFailureError 中止。
    max_workers>1: 并发执行(线程池);并发下无法定义"连续",改为累计失败达到
    abort_failure_threshold 时抛 ConsecutiveFailureError 中止。
    """
    if max_workers <= 1:
        return _translate_sequential(
            pending, translations, human, glossary, ai_translate, at=at,
            max_retries=max_retries, backoff_s=backoff_s, sleep=sleep,
            max_consecutive_failures=max_consecutive_failures,
        )

    lock = threading.Lock()
    state = {"failed": 0, "stop": False, "translated": 0}
    failures: list[str] = []

    def work(item: dict) -> None:
        if state["stop"]:
            return
        unique_name, field, en_text = item["unique_name"], item["field"], item["en"]
        human_zh = _human_get(human, unique_name, field)
        if human_zh is not None:
            with lock:
                set_translation(translations, unique_name, field, en_text, human_zh, at)
                state["translated"] += 1
            return
        try:
            zh = _call_with_retries(ai_translate, en_text, glossary, max_retries, backoff_s, sleep)
        except ai_client.AIError as e:
            with lock:
                state["failed"] += 1
                failures.append(f"{unique_name}.{field}: {e}")
                if state["failed"] >= abort_failure_threshold:
                    state["stop"] = True
            return
        with lock:
            set_translation(translations, unique_name, field, en_text, zh, at)
            state["translated"] += 1

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(work, pending))
    if state["stop"]:
        raise ConsecutiveFailureError(
            f"累计失败已达 {abort_failure_threshold} 次,API 可能不可用,已中止\n"
            + "\n".join(f"  FAIL {f}" for f in failures[-5:])
        )
    return state["translated"], failures


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _glossary_flat(glossary: dict) -> dict:
    """合并 terms/characters 两节为 {EN: 中文}."""
    flat = {}
    for section in ("terms", "characters"):
        flat.update(glossary.get(section) or {})
    return flat


def glossary_changes(old: dict, new: dict) -> dict:
    """返回 {EN: (旧中文, 新中文)} —— 只在两个表里都存在且值不同时算变更."""
    changes = {}
    old_flat, new_flat = _glossary_flat(old), _glossary_flat(new)
    for en, zh in new_flat.items():
        if en in old_flat and old_flat[en] != zh:
            changes[en] = (old_flat[en], zh)
    return changes


def apply_replacements(translations: dict, changes: dict, human: dict) -> int:
    """旧中文 -> 新中文 确定性替换所有非人工译文;返回替换的字段数.

    人工覆盖的字段(human_translations.json 命中)绝不被动.
    """
    replaced = 0
    for unique_name, fields in translations.items():
        for field, entry in fields.items():
            if _human_get(human, unique_name, field) is not None:
                continue
            zh = entry.get("zh") or ""
            new_zh = zh
            for _, (old, new) in changes.items():
                if old and old in new_zh:
                    new_zh = new_zh.replace(old, new)
            if new_zh != zh:
                entry["zh"] = new_zh
                replaced += 1
    return replaced


def find_affected_fields(translations: dict, glossary: dict, human: dict) -> list[dict]:
    """缓存中 en 原文提到任一术语表词条的字段 —— 术语表/规则变化后需要 AI 重译.

    返回 [{unique_name, field, en}];人工覆盖字段除外.
    """
    keys = sorted(_glossary_flat(glossary), key=len, reverse=True)
    affected = []
    for unique_name, fields in translations.items():
        for field, entry in fields.items():
            if _human_get(human, unique_name, field) is not None:
                continue
            en_text = entry.get("en") or ""
            if any(re.search(rf"(?<![A-Za-z]){re.escape(k)}(?![A-Za-z])", en_text)
                   for k in keys):
                affected.append({"unique_name": unique_name, "field": field, "en": en_text})
    return affected


def merge_pending(pending: list[dict], extra: list[dict]) -> None:
    """把 extra 并入 pending,按 (unique_name, field) 去重."""
    seen = {(p["unique_name"], p["field"]) for p in pending}
    for item in extra:
        if (item["unique_name"], item["field"]) not in seen:
            pending.append(item)
            seen.add((item["unique_name"], item["field"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate pending fields into translations.json")
    parser.add_argument("--pending", default="source/pending.json")
    parser.add_argument("--translations", default="source/translations.json")
    parser.add_argument("--human", default="source/human_translations.json")
    parser.add_argument("--glossary", default="source/glossary.json")
    parser.add_argument("--last-glossary", default="source/last_glossary.json",
                        help="上次应用过的术语表快照(检测术语变更用)")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="并发线程数(1=顺序;DeepSeek 等 API 可用几百上千)")
    parser.add_argument("--dry-run", action="store_true", help="只输出统计,不调用 AI")
    parser.add_argument("--at", default=None, help="ISO 时间戳,默认当前 UTC")
    args = parser.parse_args()

    pending = load_list(Path(args.pending))
    translations = load_translations(Path(args.translations))
    human = load_json(Path(args.human))
    glossary = load_json(Path(args.glossary))
    at = args.at or _now_iso()

    # 术语表变更处理: 值变更走确定性替换(零 API),格式/新增词条只重译命中字段
    last_path = Path(args.last_glossary)
    last_glossary = load_json(last_path)
    glossary_changed = bool(last_glossary) and last_glossary != glossary
    if glossary_changed:
        changes = glossary_changes(last_glossary, glossary)
        replaced = apply_replacements(translations, changes, human) if not args.dry_run else 0
        affected = find_affected_fields(translations, glossary, human)
        merge_pending(pending, affected)
        print(f"术语表变更: {len(changes)} 个词条值变更"
              f"{f'(替换 {replaced} 个字段)' if not args.dry_run else '(dry-run 不替换)'},"
              f" {len(affected)} 个命中字段并入待翻译")

    if not args.dry_run:
        missing = [k for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL")
                   if not os.environ.get(k)]
        if missing:
            print(f"缺少环境变量: {', '.join(missing)}(dry-run 不需要)")
            raise SystemExit(1)

    if args.dry_run:
        print(f"[dry-run] {len(pending)} 条待翻译,跳过 AI 调用")
        return

    def ai_translate(en_text: str, glossary: dict) -> str:
        return ai_client.translate_with_ai(
            en_text, glossary,
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["OPENAI_API_KEY"],
            model=os.environ["OPENAI_MODEL"],
        )

    try:
        translated, failures = translate_pending(
            pending, translations, human, glossary, ai_translate, at=at,
            max_workers=args.concurrency,
        )
    except ConsecutiveFailureError as e:
        save_json(Path(args.translations), translations)  # 保留已完成的进度
        print(e)
        raise SystemExit(1)
    save_json(Path(args.translations), translations)
    save_json(last_path, glossary)  # 成功后才推进术语表快照
    print(f"翻译完成: {translated} 条成功, {len(failures)} 条失败")
    for f in failures:
        print(f"  FAIL {f}")


if __name__ == "__main__":
    main()
