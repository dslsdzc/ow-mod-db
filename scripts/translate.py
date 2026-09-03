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
    lang_file,
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


def _make_chunks(items: list[dict], batch_size: int, batch_chars: int) -> list[list[dict]]:
    """按条数与字符总量双上限分块(长文本自动少装,防输出截断)."""
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0
    for item in items:
        size = len(item.get("en") or "")
        if current and (len(current) >= batch_size or current_chars + size > batch_chars):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += size
    if current:
        chunks.append(current)
    return chunks


def translate_pending_batched(pending: list[dict], translations: dict, human: dict,
                              glossary: dict, ai_batch, *, at: str, batch_size: int = 30,
                              batch_chars: int = 1200, max_retries: int = 3,
                              backoff_s: float = 2.0, sleep=time.sleep, max_workers: int = 8,
                              consecutive_chunk_abort: int = 3) -> tuple[int, list[str]]:
    """把多条文本合并成批量请求翻译(减少请求数/术语表重复开销/限流压力).

    ai_batch(texts: list[str], glossary) -> {序号: 译文};批次级失败重试;
    响应里缺失的条目记入失败。连续 consecutive_chunk_abort 个批次整体失败时
    抛 ConsecutiveFailureError 中止。人工覆盖条目直接落缓存,不进批次。
    """
    translated = 0
    failures: list[str] = []
    ai_items = []
    for item in pending:
        unique_name, field, en_text = item["unique_name"], item["field"], item["en"]
        if _human_get(human, unique_name, field) is not None:
            set_translation(translations, unique_name, field, en_text,
                            _human_get(human, unique_name, field), at)
            translated += 1
            continue
        ai_items.append(item)

    chunks = _make_chunks(ai_items, batch_size, batch_chars)
    if not chunks:
        return translated, failures

    lock = threading.Lock()
    state = {"failed_chunks": 0, "stop": False}

    def process(chunk: list[dict], depth: int = 0) -> None:
        nonlocal translated
        if state["stop"]:
            return
        result = None
        last_error = None
        for attempt in range(max_retries):
            try:
                result = ai_batch([c["en"] for c in chunk], glossary)
                break
            except ai_client.AIError as e:
                last_error = e
                sleep(backoff_s * (2 ** attempt))
        if result is not None:
            with lock:
                for idx, c in enumerate(chunk):
                    zh = result.get(idx)
                    if not zh:
                        failures.append(f"{c['unique_name']}.{c['field']}: 批次响应缺该条")
                        continue
                    set_translation(translations, c["unique_name"], c["field"], c["en"], zh, at)
                    translated += 1
            return
        # 批次整体失败 → 折半重试,把截断/坏条隔离到最小粒度(最多 4 层)
        if len(chunk) > 1 and depth < 4:
            mid = len(chunk) // 2
            process(chunk[:mid], depth + 1)
            process(chunk[mid:], depth + 1)
            return
        with lock:
            state["failed_chunks"] += 1
            for c in chunk:
                failures.append(f"{c['unique_name']}.{c['field']}: 批次失败: {last_error}")
            if state["failed_chunks"] >= consecutive_chunk_abort:
                state["stop"] = True

    def work(chunk: list[dict]) -> None:
        process(chunk)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(work, chunks))
    if state["stop"]:
        raise ConsecutiveFailureError(
            f"连续 {consecutive_chunk_abort} 个批次翻译失败,API 可能不可用,已中止\n"
            + "\n".join(f"  FAIL {f}" for f in failures[-3:])
        )
    return translated, failures


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


def apply_human_overrides(translations: dict, human: dict, at: str) -> int:
    """把已缓存译文与人工翻译对齐(人工新增/修改后,无需等字段变更即生效).

    只处理缓存里已存在的字段;未缓存的字段下次同步自动进 pending 走人工覆盖.
    返回被覆盖的字段数.
    """
    applied = 0
    for unique_name, fields in human.items():
        if not isinstance(fields, dict):
            continue
        cached_fields = translations.get(unique_name)
        if not cached_fields:
            continue
        for field, zh in fields.items():
            if not isinstance(zh, str) or not zh.strip():
                continue
            entry = cached_fields.get(field)
            if entry is not None and entry.get("zh") != zh:
                entry["zh"] = zh
                entry["at"] = at
                applied += 1
    return applied


def _samples(pending: list[dict], translations: dict, at: str, n: int = 3) -> list[tuple[str, str]]:
    """取本次运行成功翻译的最多 n 条 (en, zh) 样例,用于人工核对翻译质量."""
    out = []
    for item in pending:
        unique_name, field = item["unique_name"], item["field"]
        entry = translations.get(unique_name, {}).get(field)
        if entry and entry.get("at") == at and len(out) < n:
            out.append((item["en"], entry["zh"]))
    return out


def merge_pending(pending: list[dict], extra: list[dict]) -> None:
    """把 extra 并入 pending,按 (unique_name, field) 去重."""
    seen = {(p["unique_name"], p["field"]) for p in pending}
    for item in extra:
        if (item["unique_name"], item["field"]) not in seen:
            pending.append(item)
            seen.add((item["unique_name"], item["field"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate pending fields into translations.json")
    parser.add_argument("--lang", default="zh_cn", help="语言目录代码,如 zh_cn/ja")
    parser.add_argument("--pending", default=None)
    parser.add_argument("--translations", default=None)
    parser.add_argument("--human", default=None)
    parser.add_argument("--glossary", default=None)
    parser.add_argument("--last-glossary", default=None,
                        help="上次应用过的术语表快照(检测术语变更用)")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="并发线程数(1=顺序;DeepSeek 等 API 可用几百上千)")
    parser.add_argument("--limit", type=int, default=0,
                        help="只翻译前 N 条(0=全部;小规模试译用)")
    parser.add_argument("--batch", type=int, default=1,
                        help="每次请求合并翻译的条数(>1 走批量模式,省 token 与限流)")
    parser.add_argument("--dry-run", action="store_true", help="只输出统计,不调用 AI")
    parser.add_argument("--at", default=None, help="ISO 时间戳,默认当前 UTC")
    args = parser.parse_args()

    lang = args.lang
    pending_path = Path(args.pending) if args.pending else lang_file("pending", lang)
    translations_path = Path(args.translations) if args.translations else lang_file("translations", lang)
    human_path = Path(args.human) if args.human else lang_file("human_translations", lang)
    glossary_path = Path(args.glossary) if args.glossary else lang_file("glossary", lang)
    last_glossary_path = Path(args.last_glossary) if args.last_glossary else lang_file("last_glossary", lang)

    pending = load_list(pending_path)
    translations = load_translations(translations_path)
    human = load_json(human_path)
    glossary = load_json(glossary_path)
    at = args.at or _now_iso()

    if not args.dry_run:
        applied = apply_human_overrides(translations, human, at)
        if applied:
            print(f"人工翻译覆盖已生效: {applied} 个字段")

    # 术语表变更处理: 值变更走确定性替换(零 API),格式/新增词条只重译命中字段
    last_glossary = load_json(last_glossary_path)
    glossary_changed = bool(last_glossary) and last_glossary != glossary
    if glossary_changed:
        changes = glossary_changes(last_glossary, glossary)
        replaced = apply_replacements(translations, changes, human) if not args.dry_run else 0
        affected = find_affected_fields(translations, glossary, human)
        merge_pending(pending, affected)
        print(f"术语表变更: {len(changes)} 个词条值变更"
              f"{f'(替换 {replaced} 个字段)' if not args.dry_run else '(dry-run 不替换)'},"
              f" {len(affected)} 个命中字段并入待翻译")

    if args.limit > 0 and len(pending) > args.limit:
        print(f"--limit {args.limit}: 只翻译前 {args.limit} 条(共 {len(pending)} 条)")
        pending = pending[:args.limit]

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

    def ai_batch(texts: list, glossary: dict) -> dict:
        return ai_client.translate_batch_with_ai(
            texts, glossary,
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["OPENAI_API_KEY"],
            model=os.environ["OPENAI_MODEL"],
        )

    try:
        if args.batch > 1:
            translated, failures = translate_pending_batched(
                pending, translations, human, glossary, ai_batch, at=at,
                batch_size=args.batch, max_workers=args.concurrency,
            )
        else:
            translated, failures = translate_pending(
                pending, translations, human, glossary, ai_translate, at=at,
                max_workers=args.concurrency,
            )
    except ConsecutiveFailureError as e:
        save_json(translations_path, translations)  # 保留已完成的进度
        print(e)
        raise SystemExit(1)
    save_json(translations_path, translations)
    save_json(last_glossary_path, glossary)  # 成功后才推进术语表快照
    print(f"翻译完成: {translated} 条成功, {len(failures)} 条失败")
    for f in failures:
        print(f"  FAIL {f}")
    for en, zh in _samples(pending, translations, at):
        print(f"  样例: {en[:80]} -> {zh[:80]}")


if __name__ == "__main__":
    main()
