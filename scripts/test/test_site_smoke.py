"""构建产物冒烟测试: 跑 build 后检查 dist 产物结构。"""
import json
import re
from pathlib import Path

from patch_registry import patches_to_dict, validate_patches

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_build(tmp_path):
    """用 fixture 官方库 + 手工翻译缓存执行 build.py,产物放到 tmp_path。"""
    import build
    official = json.loads((Path(__file__).parent / "fixtures" / "official.json").read_text(encoding="utf-8"))
    translations = {
        "Alek.OWML": {
            "description": {"en": "The mod loader and mod framework for Outer Wilds",
                            "zh": "OWML 模组加载器", "at": "t"},
        },
    }
    database, mods_data = build.build_all(official, translations)
    meta = build.meta_with_lang("zh_cn", mods_data, "2026-09-02T00:00:00Z")
    assert meta["lang"] == "zh_cn"  # main() 经同一 helper 生成 meta
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "database.json").write_text(json.dumps(database, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "data" / "mods.json").write_text(
        json.dumps({"mods": mods_data, "meta": meta}, ensure_ascii=False), encoding="utf-8")
    return database, mods_data


def test_site_files_exist():
    for rel in ("index.html", "mods.html", "mod.html", "css/style.css", "js/app.js", "sw.js"):
        assert (REPO_ROOT / "site" / rel).exists(), f"缺少 site/{rel}"


def test_dist_artifacts_and_json_valid(tmp_path):
    database, mods_data = _run_build(tmp_path)
    assert '"releases"' in (tmp_path / "database.json").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "data" / "mods.json").read_text(encoding="utf-8"))
    mods = payload["mods"]
    meta = payload["meta"]
    assert meta["mods"] == len(mods_data) == 2
    assert meta["zhDescriptions"] == 1  # 仅 Alek.OWML 简介有中文
    required_keys = {"uniqueName", "name", "originalName", "description", "authorDisplay", "downloadUrl",
                     "repo", "tags", "slug", "thumbnail", "downloadCount", "installCount",
                     "weeklyInstallCount", "version", "latestReleaseDate", "firstReleaseDate",
                     "latestReleaseDescription", "readmeDownloadUrl", "parent", "repoVariations"}
    for mod in mods:
        assert set(mod.keys()) == required_keys


def test_mirror_pages_cover_three_views():
    index = (REPO_ROOT / "site" / "index.html").read_text(encoding="utf-8")
    mods = (REPO_ROOT / "site" / "mods.html").read_text(encoding="utf-8")
    assert "featured" in index   # 首页三栏
    assert "mod-grid" in mods    # 列表页网格
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert "uniqueName" in js    # 详情页从 URL 参数读 uniqueName


def test_patch_block_markers_present():
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert "patches.json" in js
    assert "initPatchBlock" in js
    assert "owmods://install-mod/" in js
    assert "中文支持" in js


def test_i18n_framework_markers():
    i18n = (REPO_ROOT / "site" / "js" / "i18n.js").read_text(encoding="utf-8")
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    index = (REPO_ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert '"zh-CN"' in i18n and '"ja"' in i18n
    assert 'lang-switch' in i18n
    assert 'window.t' in js or 't(' in js
    assert 'js/i18n.js' in index


def test_jams_page_markers():
    html = (REPO_ROOT / "site" / "jams.html").read_text(encoding="utf-8")
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'id="jams"' in html
    assert "jamKey" in js and "renderJams" in js
    assert "jam_content.json" in js


def test_search_matches_original_english_name():
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert "originalName" in js  # 搜索匹配英文原名
    html = (REPO_ROOT / "site" / "mods.html").read_text(encoding="utf-8")
    assert "英文原名" in html     # placeholder 提示


def test_thumbnail_load_strategy_and_sw_markers():
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert "setupLazyThumbs" in js and "data-src" in js     # 手动提前预载
    assert "fetchpriority" in js                            # 首屏图优先
    assert "serviceWorker" in js                            # SW 注册
    sw = (REPO_ROOT / "site" / "sw.js").read_text(encoding="utf-8")
    assert "thumbnails" in sw and "caches" in sw and "skipWaiting" in sw
    for page in ("index.html", "mods.html", "mod.html"):
        html = (REPO_ROOT / "site" / page).read_text(encoding="utf-8")
        assert "preconnect" in html                         # 预连接图片域


def test_sw_caches_assets_and_pages():
    sw = (REPO_ROOT / "site" / "sw.js").read_text(encoding="utf-8")
    assert "ow-assets" in sw and "ow-pages" in sw          # 静态资源 + 页面缓存桶
    assert 'searchParams.has("v")' in sw                    # 版本化资源
    assert "(png|svg" in sw                                 # 无版本戳图片(占位图等)也进缓存
    assert "navigate" in sw                                 # HTML network-first
    assert "ASSET_MAX" in sw and "PAGE_MAX" in sw           # 上限清理


def test_speculation_rules_markers():
    for page in ("index.html", "mods.html", "jams.html", "mod.html"):
        html = (REPO_ROOT / "site" / page).read_text(encoding="utf-8")
        assert "speculationrules" in html and "mod.html*" in html


def test_detail_ux_markers():
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert "issues/new?template=translation.md" in js    # 报告翻译问题入口
    assert "searchTimer" in js                            # 搜索防抖
    assert 'img.loading = "lazy"' in js                   # README 图片懒加载
    assert "navigator.share" in js and "share-btn" in js  # 分享按钮(Web Share + 复制兜底)
    assert "trend-section" in js and "downloads.json" in js  # 下载趋势(官方统计 API 按需加载)
    tmpl = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "translation.md"
    assert tmpl.exists()                                  # issue 模板


def test_static_mod_page_markers():
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'href="mod/' in js                                # 卡片链接指向静态详情页
    assert "\\/mod\\/" in js                                 # 静态页 URL 路径解析
    for page in ("index.html", "mods.html", "mod.html", "jams.html"):
        html = (REPO_ROOT / "site" / page).read_text(encoding="utf-8")
        assert '"./mod/*"' in html                            # 预渲染覆盖静态页


def test_a11y_markers():
    css = (REPO_ROOT / "site" / "css" / "style.css").read_text(encoding="utf-8")
    assert ".sr-only" in css and ".skip-link" in css and "focus-visible" in css
    for page in ("index.html", "mods.html", "mod.html", "jams.html", "mod-manager.html", "404.html"):
        html = (REPO_ROOT / "site" / page).read_text(encoding="utf-8")
        assert 'class="skip-link"' in html                  # 跳转链接
        assert "data-i18n-aria-label" in html               # 导航区域名
    mods = (REPO_ROOT / "site" / "mods.html").read_text(encoding="utf-8")
    assert "aria-live" in mods and 'for="search"' in mods   # 结果数播报 + 表单标签
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert "aria-pressed" in js                             # 筛选 chips 状态
    i18n = (REPO_ROOT / "site" / "js" / "i18n.js").read_text(encoding="utf-8")
    assert "a11y.skip" in i18n and "i18nAriaLabel" in i18n


def test_i18n_dict_keys_aligned():
    """zh-CN 与 ja 词典的 key 必须一一对应(防止新增界面文案漏翻一种语言)。"""
    src = (REPO_ROOT / "site" / "js" / "i18n.js").read_text(encoding="utf-8")
    zh_block = src.split('"zh-CN": {', 1)[1].split('},\n  "ja": {', 1)[0]
    ja_block = src.split('"ja": {', 1)[1].split("};", 1)[0]
    zh_keys = set(re.findall(r'"([\w.\-]+)":', zh_block))
    ja_keys = set(re.findall(r'"([\w.\-]+)":', ja_block))
    assert zh_keys and ja_keys
    assert zh_keys == ja_keys, f"词典不一致: 仅zh={sorted(zh_keys - ja_keys)} 仅ja={sorted(ja_keys - zh_keys)}"


def test_app_js_hardcoded_ui_now_goes_through_i18n():
    """抽查已知界面文案已接入 i18n(配合 e2e 的 ja 运行时泄漏检测共同防回潮)。"""
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    for need in ('t("home.total"', 't("home.syncInfo"', 't("detail.downloadZip")',
                 't("detail.repoLink")', 't("jams.groupNote"', 't("patch.install")',
                 't("detail.comments")', 't("backTop")', 't("readme.aiNote"',
                 't("releases.showAll"', 't("site.name")'):
        assert need in js, f"未接入 i18n: {need}"


def test_all_referenced_i18n_keys_are_defined():
    """app.js 与页面里引用的所有 i18n key 必须存在于词典(防 key 泄漏到界面, 如曾出现的 jams.title)。"""
    i18n = (REPO_ROOT / "site" / "js" / "i18n.js").read_text(encoding="utf-8")
    zh_block = i18n.split('"zh-CN": {', 1)[1].split('},\n  "ja": {', 1)[0]
    defined = set(re.findall(r'"([\w.\-]+)":', zh_block))
    assert defined

    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    used_js = set(re.findall(r'\bt\("([\w.\-]+)"', js))
    assert not (used_js - defined), f"app.js 引用未定义 key: {sorted(used_js - defined)}"

    for path in sorted((REPO_ROOT / "site").glob("*.html")):
        html = path.read_text(encoding="utf-8")
        used = set(re.findall(r'data-i18n(?:-placeholder|-aria-label|-title)?="([\w.\-]+)"', html))
        assert not (used - defined), f"{path.name} 引用未定义 key: {sorted(used - defined)}"


def test_official_mod_links_rewritten_markers():
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert "rewriteOfficialModLinks" in js
    assert "__slugMap" in js
    assert "outerwildsmods.com/mods/" in js


def test_patches_payload_shape():
    patches = [
        {"target": "Hawkbar.GhostInTheMachine",
         "patch": {"uniqueName": "yyy.CN", "name": "补丁", "install": "owmm",
                   "url": "", "note": "", "addedAt": ""}},
    ]
    assert validate_patches(patches, {"Hawkbar.GhostInTheMachine", "yyy.CN"}) == []
    payload = patches_to_dict(patches)
    assert payload == {"Hawkbar.GhostInTheMachine": payload["Hawkbar.GhostInTheMachine"]}
    assert payload["Hawkbar.GhostInTheMachine"]["uniqueName"] == "yyy.CN"
    assert patches_to_dict([]) == {}


def test_site_data_dir_drives_outputs(tmp_path, monkeypatch):
    import build
    official = json.loads((Path(__file__).parent / "fixtures" / "official.json").read_text(encoding="utf-8"))
    en_db, en_mods = build.build_all(official, {})          # en = 无翻译
    assert en_db["releases"][0]["description"].startswith("The mod loader")
    assert en_mods[0]["description"].startswith("The mod loader")


def test_patches_payload_missing_or_broken_is_empty(tmp_path, capsys):
    import build
    assert build.patches_payload(tmp_path / "nope.json", {"releases": []}) == {}
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert build.patches_payload(broken, {"releases": []}) == {}
    assert "解析失败" in capsys.readouterr().out


def test_patches_payload_valid_registry_maps_targets(tmp_path):
    import build
    registry = tmp_path / "patches.json"
    registry.write_text(json.dumps([
        {"target": "Hawkbar.GhostInTheMachine",
         "patch": {"uniqueName": "yyy.CN", "name": "补丁", "install": "owmm",
                   "url": "", "note": "", "addedAt": ""}},
    ]), encoding="utf-8")
    official = {"releases": [{"uniqueName": "Hawkbar.GhostInTheMachine"}]}
    payload = build.patches_payload(registry, official)
    assert list(payload) == ["Hawkbar.GhostInTheMachine"]
    assert payload["Hawkbar.GhostInTheMachine"]["uniqueName"] == "yyy.CN"


def test_site_data_lang_routing_markers():
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    i18n = (REPO_ROOT / "site" / "js" / "i18n.js").read_text(encoding="utf-8")
    assert "contentUrl" in js and "fetchContent" in js
    assert "zh_cn" in i18n and "LANG_DIR_CODE" in i18n
