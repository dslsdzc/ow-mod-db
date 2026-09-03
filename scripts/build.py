"""Merge official db + translations into per-language website data and database.json.

Output layout (multi-language):
- zh_cn: 根路径不变 — dist/database.json(OWMM URL)+ dist/data/…(中文)
- ja:    dist/data/ja/…(source/ja 翻译缓存;缺失时回退官方原文)
- en:    dist/data/en/…(官方原文,翻译恒为空)
site 静态资源只部署一次到 dist 根。
"""

import argparse
import json
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
LANGS = ["zh_cn", "ja", "en"]  # en 为回退用的官方原文(翻译为空)
_CJK = re.compile(r"[一-鿿]")


def translate_mod(mod: dict, translations: dict) -> dict:
    out = dict(mod)
    unique_name = mod.get("uniqueName", "")
    for field in TRANSLATABLE_FIELDS:
        zh = get_translation(translations, unique_name, field)
        if zh:
            out[field] = zh
    return out


def build_all(official: dict, translations: dict) -> tuple[dict, list[dict]]:
    database_lang = dict(official)
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
        database_lang[group] = out_group
    return database_lang, mods_data


def meta_with_lang(lang: str, mods: list[dict], generated_at: str) -> dict:
    """单语言 mods.json 的 meta;zhDescriptions 统计该语言下含中文的简介数。"""
    return {
        "generatedAt": generated_at,
        "mods": len(mods),
        "zhDescriptions": sum(1 for m in mods if _CJK.search(m.get("description") or "")),
        "lang": lang,
    }


def patches_payload(path: Path, official: dict) -> dict:
    """解析并校验汉化补丁注册表(target -> patch);失败只打印不阻塞,返回 {}。"""
    from patch_registry import patches_to_dict, validate_patches

    if not path.exists():
        return {}
    try:
        patches = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"  注册表解析失败(按空表处理): {e}")
        patches = []
    if not isinstance(patches, list):
        print(f"  注册表顶层不是数组(按空表处理): {type(patches).__name__}")
        patches = []
    ids = {m.get("uniqueName", "") for m in official.get("releases", [])}
    for e in validate_patches(patches, ids):
        print(f"  注册表校验: {e}")
    return patches_to_dict(patches)


def deploy_site(site_dir: Path, dist_dir: Path) -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)
    for item in site_dir.iterdir():
        target = dist_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate per-language site data and zh database.json")
    parser.add_argument("--lang", default="zh_cn",
                        help="语言目录代码(兼容保留;构建固定输出 zh_cn/ja/en 全部语言目录)")
    parser.add_argument("--official", default="source/official.json")
    parser.add_argument("--licenses", default="source/license_cache.json")
    parser.add_argument("--patches", default="source/translation_patches.json",
                        help="中文汉化补丁注册表(语言无关,各语言目录均写入)")
    parser.add_argument("--site", default=str(SITE_SOURCE))
    parser.add_argument("--dist", default=str(DIST))
    args = parser.parse_args()

    official = load_json(Path(args.official))
    dist = Path(args.dist)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    zh_mod_count = 0

    for lang in LANGS:
        translations = {}
        if lang != "en":
            translations = load_translations(lang_file("translations", lang)) \
                if lang_file("translations", lang).exists() else {}
        database_lang, mods_lang = build_all(official, translations)
        if lang == "zh_cn":
            zh_mod_count = len(mods_lang)
        data_dir = dist / site_data_dir(lang)
        (data_dir / "releases").mkdir(parents=True, exist_ok=True)
        save_json(data_dir / "mods.json", {"mods": mods_lang, "meta": meta_with_lang(lang, mods_lang, generated_at)})
        if lang == "zh_cn":
            save_json(dist / "database.json", database_lang)  # 保持 OWMM URL(仅中文版)
        # 版本历史: 每 mod 独立小文件,详情页按需加载(各语言缓存各自成目录)
        releases = load_json(lang_file("releases_cache", lang))
        rel_dir = data_dir / "releases"
        for unique_name, entry in releases.items():
            if isinstance(entry, dict) and entry.get("releases"):
                save_json(rel_dir / f"{unique_name}.json", entry)
        # 汉化补丁注册表(target -> patch);校验只打印,不阻塞构建
        save_json(data_dir / "patches.json", patches_payload(Path(args.patches), official))
        # README 缓存与许可信息、Jam 数据(详情页/活动页用;无对应语言文件则为空表)
        readmes = load_json(lang_file("readmes", lang))
        save_json(data_dir / "readmes.json", readmes)
        save_json(data_dir / "licenses.json", load_json(Path(args.licenses)))
        save_json(data_dir / "jams.json", load_json(lang_file("jams", lang)))
        save_json(data_dir / "jam_content.json", load_json(lang_file("jam_content", lang)))

    deploy_site(Path(args.site), dist)
    # 静态资源与数据接口加版本号: 界面不缓存,图片(不在此列)可缓存
    stamp = generated_at.replace(":", "").replace("-", "").replace(".", "Z")[:17]
    for html in dist.glob("*.html"):
        text = html.read_text(encoding="utf-8")
        text = text.replace('src="js/app.js"', f'src="js/app.js?v={stamp}"')
        text = text.replace('href="css/style.css"', f'href="css/style.css?v={stamp}"')
        if 'window.DATA_V' not in text:
            text = text.replace("<head>", f'<head>\n<script>window.DATA_V = "{stamp}";</script>', 1)
        html.write_text(text, encoding="utf-8")
    print(f"已生成 {dist/'database.json'}(zh_cn)与站点数据 {', '.join(site_data_dir(l) for l in LANGS)},"
          f"MOD 数: {zh_mod_count}")


if __name__ == "__main__":
    main()
