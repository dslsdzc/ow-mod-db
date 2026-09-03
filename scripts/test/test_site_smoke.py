"""构建产物冒烟测试: 跑 build 后检查 dist 产物结构。"""
import json
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
    for rel in ("index.html", "mods.html", "mod.html", "css/style.css", "js/app.js"):
        assert (REPO_ROOT / "site" / rel).exists(), f"缺少 site/{rel}"


def test_dist_artifacts_and_json_valid(tmp_path):
    database, mods_data = _run_build(tmp_path)
    assert '"releases"' in (tmp_path / "database.json").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "data" / "mods.json").read_text(encoding="utf-8"))
    mods = payload["mods"]
    meta = payload["meta"]
    assert meta["mods"] == len(mods_data) == 2
    assert meta["zhDescriptions"] == 1  # 仅 Alek.OWML 简介有中文
    required_keys = {"uniqueName", "name", "description", "authorDisplay", "downloadUrl",
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
