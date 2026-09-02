"""Merge official db + translations into Chinese database.json and site data."""

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from translation_store import (
    TRANSLATABLE_FIELDS,
    get_translation,
    load_json,
    load_translations,
    save_json,
)

SITE_SOURCE = Path("site")
DIST = Path("dist")


def translate_mod(mod: dict, translations: dict) -> dict:
    out = dict(mod)
    unique_name = mod.get("uniqueName", "")
    for field in TRANSLATABLE_FIELDS:
        zh = get_translation(translations, unique_name, field)
        if zh:
            out[field] = zh
    return out


def build_all(official: dict, translations: dict) -> tuple[dict, list[dict]]:
    database_zh = dict(official)
    mods_data = []
    for group in ("releases", "alphaReleases"):
        out_group = []
        for mod in official.get(group, []):
            out_mod = translate_mod(mod, translations)
            out_group.append(out_mod)
            if group == "releases":
                mods_data.append({
                    "uniqueName": out_mod.get("uniqueName", ""),
                    "name": out_mod.get("name", ""),
                    "description": out_mod.get("description", ""),
                    "authorDisplay": out_mod.get("authorDisplay") or out_mod.get("author", ""),
                    "downloadUrl": out_mod.get("downloadUrl", ""),
                    "repo": out_mod.get("repo", ""),
                    "tags": out_mod.get("tags", []),
                    "slug": out_mod.get("slug", ""),
                    "thumbnail": out_mod.get("thumbnail", {}),
                    "downloadCount": out_mod.get("downloadCount", 0),
                    "installCount": out_mod.get("installCount", 0),
                    "weeklyInstallCount": out_mod.get("weeklyInstallCount", 0),
                    "version": str(out_mod.get("version") or "").removeprefix("v"),
                    "latestReleaseDate": out_mod.get("latestReleaseDate", ""),
                    "firstReleaseDate": out_mod.get("firstReleaseDate", ""),
                    "latestReleaseDescription": out_mod.get("latestReleaseDescription", ""),
                    "readmeDownloadUrl": (out_mod.get("readme") or {}).get("downloadUrl", ""),
                    "parent": out_mod.get("parent", ""),
                    "repoVariations": out_mod.get("repoVariations", []),
                })
        database_zh[group] = out_group
    return database_zh, mods_data


def deploy_site(site_dir: Path, dist_dir: Path) -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)
    for item in site_dir.iterdir():
        target = dist_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Chinese database.json and website data")
    parser.add_argument("--official", default="source/official.json")
    parser.add_argument("--translations", default="source/translations.json")
    parser.add_argument("--readmes", default="source/readmes.json")
    parser.add_argument("--licenses", default="source/license_cache.json")
    parser.add_argument("--releases", default="source/releases_cache.json")
    parser.add_argument("--patches", default="source/translation_patches.json",
                        help="中文汉化补丁注册表")
    parser.add_argument("--site", default=str(SITE_SOURCE))
    parser.add_argument("--dist", default=str(DIST))
    args = parser.parse_args()

    official = load_json(Path(args.official))
    translations = load_translations(Path(args.translations))
    database_zh, mods_data = build_all(official, translations)

    dist = Path(args.dist)
    (dist / "data").mkdir(parents=True, exist_ok=True)
    cjk = re.compile(r"[一-鿿]")
    meta = {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mods": len(mods_data),
        "zhDescriptions": sum(1 for m in mods_data if cjk.search(m.get("description") or "")),
    }
    save_json(dist / "database.json", database_zh)
    save_json(dist / "data" / "mods.json", {"mods": mods_data, "meta": meta})
    # 版本历史: 每 mod 独立小文件,详情页按需加载
    releases = load_json(Path(args.releases))
    rel_dir = dist / "data" / "releases"
    rel_dir.mkdir(parents=True, exist_ok=True)
    for unique_name, entry in releases.items():
        if isinstance(entry, dict) and entry.get("releases"):
            save_json(rel_dir / f"{unique_name}.json", entry)
    # 中文汉化补丁注册表(target -> patch;空表为 {});校验只打印,不阻塞构建
    import json as _json
    from patch_registry import patches_to_dict, validate_patches
    _patch_path = Path(args.patches)
    patches = []
    if _patch_path.exists():
        try:
            patches = _json.loads(_patch_path.read_text(encoding="utf-8"))
        except (ValueError, _json.JSONDecodeError) as _e:
            print(f"  注册表解析失败(按空表处理): {_e}")
            patches = []
        if not isinstance(patches, list):
            print(f"  注册表顶层不是数组(按空表处理): {type(patches).__name__}")
            patches = []
        _ids = {m.get("uniqueName", "") for m in official.get("releases", [])}
        for _e in validate_patches(patches, _ids):
            print(f"  注册表校验: {_e}")
    save_json(dist / "data" / "patches.json", patches_to_dict(patches))
    # README 中文缓存与许可信息(详情页用;readmes 由 scripts/readmes.py 生成)
    readmes = load_json(Path(args.readmes))
    licenses = load_json(Path(args.licenses))
    save_json(dist / "data" / "readmes.json", readmes)
    save_json(dist / "data" / "licenses.json", licenses)
    deploy_site(Path(args.site), dist)
    print(f"已生成 {dist/'database.json'} 与 {dist/'data'/'mods.json'},MOD 数: {len(mods_data)}")


if __name__ == "__main__":
    main()
