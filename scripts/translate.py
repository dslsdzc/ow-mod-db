"""Translate pending fields: human overrides first, then AI with glossary."""

import argparse
import os
import time
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


def translate_pending(pending: list[dict], translations: dict, human: dict, glossary: dict,
                      ai_translate, *, at: str, max_retries: int = 3, backoff_s: float = 2.0,
                      sleep=time.sleep) -> tuple[int, list[str]]:
    """Translate each pending item. Returns (translated_count, failure_messages).

    Failed items are left untranslated (English kept) and reported, not fatal.
    """
    translated = 0
    failures = []
    for item in pending:
        unique_name, field, en_text = item["unique_name"], item["field"], item["en"]
        human_zh = _human_get(human, unique_name, field)
        if human_zh is not None:
            set_translation(translations, unique_name, field, en_text, human_zh, at)
            translated += 1
            continue
        try:
            zh = _call_with_retries(ai_translate, en_text, glossary, max_retries, backoff_s, sleep)
        except ai_client.AIError as e:
            failures.append(f"{unique_name}.{field}: {e}")
            continue
        set_translation(translations, unique_name, field, en_text, zh, at)
        translated += 1
    return translated, failures


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate pending fields into translations.json")
    parser.add_argument("--pending", default="source/pending.json")
    parser.add_argument("--translations", default="source/translations.json")
    parser.add_argument("--human", default="source/human_translations.json")
    parser.add_argument("--glossary", default="source/glossary.json")
    parser.add_argument("--dry-run", action="store_true", help="只输出统计,不调用 AI")
    parser.add_argument("--at", default=None, help="ISO 时间戳,默认当前 UTC")
    args = parser.parse_args()

    pending = load_list(Path(args.pending))
    translations = load_translations(Path(args.translations))
    human = load_json(Path(args.human))
    glossary = load_json(Path(args.glossary))
    at = args.at or _now_iso()

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

    translated, failures = translate_pending(
        pending, translations, human, glossary, ai_translate, at=at
    )
    save_json(Path(args.translations), translations)
    print(f"翻译完成: {translated} 条成功, {len(failures)} 条失败")
    for f in failures:
        print(f"  FAIL {f}")


if __name__ == "__main__":
    main()
