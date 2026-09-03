"""Merge official db + translations into Chinese database.json and site data."""

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from translation_store import (
    TRANSLATABLE_FIELDS,
    get_translation,
    lang_file,
    load_json,
    load_translations,
    save_json,
    site_data_dir,
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
    parser.add_argument("--lang", default="zh_cn", help="语言目录代码,如 zh_cn/ja")
    parser.add_argument("--official", default="source/official.json")
    parser.add_argument("--translations", default=None)
    parser.add_argument("--readmes", default=None)
    parser.add_argument("--licenses", default="source/license_cache.json")
    parser.add_argument("--jams", default=None)
    parser.add_argument("--jam-content", default=None)
    parser.add_argument("--releases", default=None)
    parser.add_argument("--patches", default="source/translation_patches.json",
                        help="中文汉化补丁注册表(语言无关,根目录)")
    parser.add_argument("--site", default=str(SITE_SOURCE))
    parser.add_argument("--dist", default=str(DIST))
    args = parser.parse_args()

    lang = args.lang
    translations_path = Path(args.translations) if args.translations else lang_file("translations", lang)
    readmes_path = Path(args.readmes) if args.readmes else lang_file("readmes", lang)
    releases_path = Path(args.releases) if args.releases else lang_file("releases_cache", lang)
    jams_path = Path(args.jams) if args.jams else lang_file("jams", lang)
    jam_content_path = Path(args.jam_content) if args.jam_content else lang_file("jam_content", lang)

    official = load_json(Path(args.official))
    translations = load_translations(translations_path)
    database_zh, mods_data = build_all(official, translations)

    dist = Path(args.dist)
    data_dir = dist / site_data_dir(lang)
    data_dir.mkdir(parents=True, exist_ok=True)
    cjk = re.compile(r"[一-鿿]")
    meta = {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mods": len(mods_data),
        "zhDescriptions": sum(1 for m in mods_data if cjk.search(m.get("description") or "")),
    }
    save_json(dist / "database.json", database_zh)
    save_json(data_dir / "mods.json", {"mods": mods_data, "meta": meta})
    # 版本历史: 每 mod 独立小文件,详情页按需加载
    releases = load_json(releases_path)
    rel_dir = data_dir / "releases"
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
    save_json(data_dir / "patches.json", patches_to_dict(patches))
    # README 中文缓存与许可信息(详情页用;readmes 由 scripts/readmes.py 生成)
    readmes = load_json(readmes_path)
    licenses = load_json(Path(args.licenses))
    save_json(data_dir / "readmes.json", readmes)
    save_json(data_dir / "licenses.json", licenses)
    jams = load_json(jams_path) if jams_path.exists() else {}
    save_json(data_dir / "jams.json", jams)
    jam_content = load_json(jam_content_path) if jam_content_path.exists() else {}
    save_json(data_dir / "jam_content.json", jam_content)
    deploy_site(Path(args.site), dist)
    # 静态资源与数据接口加版本号: 界面不缓存,图片(不在此列)可缓存
    stamp = meta["generatedAt"].replace(":", "").replace("-", "").replace(".", "Z")[:17]
    for html in dist.glob("*.html"):
        text = html.read_text(encoding="utf-8")
        text = text.replace('src="js/app.js"', f'src="js/app.js?v={stamp}"')
        text = text.replace('href="css/style.css"', f'href="css/style.css?v={stamp}"')
        if 'window.DATA_V' not in text:
            text = text.replace("<head>", f'<head>\n<script>window.DATA_V = "{stamp}";</script>', 1)
        html.write_text(text, encoding="utf-8")
    print(f"已生成 {dist/'database.json'} 与 {dist/'data'/'mods.json'},MOD 数: {len(mods_data)}")


if __name__ == "__main__":
    main()
