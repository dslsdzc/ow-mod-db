"""Sync official database and compute translation diffs."""

import argparse
from pathlib import Path

import httpx

from translation_store import (
    TRANSLATABLE_FIELDS,
    lang_file,
    load_json,
    load_translations,
    needs_translation,
    save_json,
    save_list,
)

OFFICIAL_DB_URL = "https://ow-mods.github.io/ow-mod-db/database.json"


def fetch_official(url: str = OFFICIAL_DB_URL) -> dict:
    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict) or "releases" not in data:
        raise ValueError("unexpected official database format")
    return data


def validate_official(data: dict) -> list[str]:
    """官方库结构校验: 返回警告列表(不抛错; 顶层结构问题由 fetch_official 把关)。

    上游数据异常时给出可读提示,避免静默生成坏数据或构建时才发现。
    """
    warns = []
    for group in ("releases", "alphaReleases"):
        mods = data.get(group)
        if mods is None:
            warns.append(f"缺少 {group} 分组")
            continue
        if not isinstance(mods, list):
            warns.append(f"{group} 不是数组")
            continue
        seen: set[str] = set()
        no_uid = no_name = dup = non_dict = 0
        for mod in mods:
            if not isinstance(mod, dict):
                non_dict += 1
                continue
            uid = mod.get("uniqueName")
            if not uid:
                no_uid += 1
            elif uid in seen:
                dup += 1
            else:
                seen.add(uid)
            if not str(mod.get("name") or "").strip():
                no_name += 1
        if non_dict:
            warns.append(f"{group}: {non_dict} 个非对象条目")
        if no_uid:
            warns.append(f"{group}: {no_uid} 个条目缺 uniqueName")
        if dup:
            warns.append(f"{group}: {dup} 个条目 uniqueName 重复")
        if no_name:
            warns.append(f"{group}: {no_name} 个条目缺 name")
    return warns


def diff_database(official: dict, translations: dict) -> list[dict]:
    """Return [{unique_name, field, en}] for fields that changed or are new."""
    pending = []
    for group in ("releases", "alphaReleases"):
        for mod in official.get(group, []):
            unique_name = mod.get("uniqueName")
            if not unique_name:
                continue
            for field in TRANSLATABLE_FIELDS:
                en_text = mod.get(field) or ""
                if needs_translation(translations, unique_name, field, en_text):
                    pending.append({"unique_name": unique_name, "field": field, "en": en_text})
    return pending


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync official db and write pending translations")
    parser.add_argument("--lang", default="zh_cn", help="语言目录代码,如 zh_cn/ja")
    parser.add_argument("--official", default=OFFICIAL_DB_URL, help="official database.json URL or local path")
    parser.add_argument("--translations", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--save-official", default="source/official.json", help="snapshot for build.py")
    args = parser.parse_args()

    lang = args.lang
    translations_path = Path(args.translations) if args.translations else lang_file("translations", lang)
    pending_path = Path(args.out) if args.out else lang_file("pending", lang)

    if args.official.startswith("http"):
        official = fetch_official(args.official)
    else:
        official = load_json(Path(args.official))

    for warning in validate_official(official):
        print(f"  官方库校验警告: {warning}")

    translations = load_translations(translations_path)
    pending = diff_database(official, translations)
    save_list(pending_path, pending)
    save_json(Path(args.save_official), official)
    print(f"{len(pending)} pending translations")
    for item in pending[:5]:
        print(f"  {item['unique_name']}.{item['field']}")


if __name__ == "__main__":
    main()
