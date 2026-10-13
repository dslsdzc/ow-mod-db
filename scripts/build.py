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
from html import escape as html_escape
from pathlib import Path
from urllib.parse import quote

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
SITE_URL = "https://dslsdzc.github.io/ow-mod-db"
MOD_PAGE_DIR = "mod"
_SAFE_FILENAME = re.compile(r'[/\\:*?"<>|\s]')  # 文件名不安全字符(含空白)
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
                    "originalName": mod.get("name", ""),  # 官方英文原名(供搜索,不随译名变)
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


# ---- 静态详情页与 SEO 文件(爬虫/社交抓取友好; 页面 JS 加载后接管渲染) ----

_MOD_PAGE_MARKERS = (
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    "<title>MOD 详情 — 星际拓荒 MOD 数据库</title>",
    '<meta property="og:title" content="MOD 详情 — 星际拓荒 MOD 数据库">',
    f'<meta property="og:image" content="{SITE_URL}/og.png">',
    '<main id="detail"></main>',
)


def mod_page_filename(unique_name: str) -> str:
    """uniqueName -> 静态页文件名; 含不安全字符时返回空串(跳过静态页,老式链接仍可用)。"""
    return "" if not unique_name or _SAFE_FILENAME.search(unique_name) else unique_name + ".html"


def build_mod_pages(template: str, mods: list[dict], translations: dict, dist: Path,
                    site_url: str = SITE_URL) -> int:
    """按 mod.html 模板为每个 mod 生成 dist/mod/<uniqueName>.html。

    静态页带定制 title/og/canonical 与一段无 JS 可见的正文; 以 <base href="../">
    让 css/js/data 相对路径继续相对站点根解析。返回生成页数。
    """
    missing = [m for m in _MOD_PAGE_MARKERS if m not in template]
    if missing:
        raise ValueError(f"mod.html 模板缺少预期标记({len(missing)} 处),静态页生成中止")
    out_dir = dist / MOD_PAGE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.html"):
        stale.unlink()  # 清理已不复存在的 mod 的旧页面(本地增量构建场景)
    count = 0
    for mod in mods:
        filename = mod_page_filename(mod.get("uniqueName") or "")
        if not filename:
            continue
        out = translate_mod(mod, translations)
        name = str(out.get("name") or out.get("uniqueName") or "")
        desc = str(out.get("description") or "").strip()
        author = str(out.get("authorDisplay") or out.get("author") or "")
        version = str(out.get("version") or "").removeprefix("v")
        thumb = (mod.get("thumbnail") or {}).get("main") or ""
        og_image = (f"https://ow-mods.github.io/ow-mod-db/thumbnails/{thumb}"
                    if thumb else f"{site_url}/og.png")
        page_url = f"{site_url}/{MOD_PAGE_DIR}/{quote(mod.get('uniqueName') or '')}.html"
        title = f"{name} — 星际拓荒 MOD 数据库"
        lead = desc[:140] + ("…" if len(desc) > 140 else "")
        meta_line = f"{author} · v{version}" if version else author

        html = template
        html = html.replace(
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n<base href="../">', 1)
        html = html.replace("<title>MOD 详情 — 星际拓荒 MOD 数据库</title>",
                            f"<title>{html_escape(title)}</title>", 1)
        html = html.replace('<meta property="og:title" content="MOD 详情 — 星际拓荒 MOD 数据库">',
                            f'<meta property="og:title" content="{html_escape(title)}">', 1)
        html = html.replace(f'<meta property="og:image" content="{site_url}/og.png">',
                            f'<meta property="og:image" content="{html_escape(og_image)}">\n'
                            f'<meta property="og:description" content="{html_escape(lead)}">\n'
                            f'<meta property="og:url" content="{html_escape(page_url)}">\n'
                            f'<link rel="canonical" href="{html_escape(page_url)}">', 1)
        # 静态页之间不预渲染; 预渲染规则由根页面覆盖"列表 -> 详情"主路径
        html = re.sub(r'<script type="speculationrules">.*?</script>\n', "", html, count=1, flags=re.S)
        static_body = (
            '<div class="detail">'
            f"<h1>{html_escape(name)}</h1>"
            f'<div class="meta">{html_escape(meta_line)}</div>'
            f"<p>{html_escape(desc)}</p>"
            '<p><a class="link" href="mods.html">← 返回全部 MOD</a></p>'
            "</div>")
        html = html.replace('<main id="detail"></main>',
                            f'<main id="detail">{static_body}</main>', 1)
        (out_dir / filename).write_text(html, encoding="utf-8")
        count += 1
    return count


def build_seo_files(dist: Path, mods: list[dict], generated_at: str,
                    site_url: str = SITE_URL) -> None:
    """生成 sitemap.xml(主页/列表/活动页 + 全部静态详情页)与 robots.txt。"""
    lastmod = generated_at[:10]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for rel in ("", "mods.html", "jams.html", "mod-manager.html"):
        loc = f"{site_url}/{rel}" if rel else site_url + "/"
        lines.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    for mod in mods:
        filename = mod_page_filename(mod.get("uniqueName") or "")
        if not filename:
            continue
        uid = quote(mod.get("uniqueName") or "")
        lines.append(f"  <url><loc>{site_url}/{MOD_PAGE_DIR}/{uid}.html</loc>"
                     f"<lastmod>{lastmod}</lastmod></url>")
    lines.append("</urlset>")
    (dist / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (dist / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: " + site_url + "/sitemap.xml\n", encoding="utf-8")


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
    # 静态详情页(SEO/社交抓取; 所有界面语言共享同一页面, JS 按所选语言取数渲染)
    template = (Path(args.site) / "mod.html").read_text(encoding="utf-8")
    zh_path = lang_file("translations", "zh_cn")
    zh_translations = load_translations(zh_path) if zh_path.exists() else {}
    page_count = build_mod_pages(template, official.get("releases", []), zh_translations, dist)
    build_seo_files(dist, official.get("releases", []), generated_at)
    # 静态资源与数据接口加版本号: 界面不缓存,图片(不在此列)可缓存; 含静态详情页
    stamp = generated_at.replace(":", "").replace("-", "").replace(".", "Z")[:17]
    for html in list(dist.glob("*.html")) + list((dist / "mod").glob("*.html")):
        text = html.read_text(encoding="utf-8")
        text = text.replace('src="js/app.js"', f'src="js/app.js?v={stamp}"')
        text = text.replace('href="css/style.css"', f'href="css/style.css?v={stamp}"')
        if 'window.DATA_V' not in text:
            text = text.replace("<head>", f'<head>\n<script>window.DATA_V = "{stamp}";</script>', 1)
        html.write_text(text, encoding="utf-8")
    print(f"已生成 {dist/'database.json'}(zh_cn)与站点数据 {', '.join(site_data_dir(l) for l in LANGS)},"
          f"MOD 数: {zh_mod_count},静态详情页: {page_count}")


if __name__ == "__main__":
    main()
