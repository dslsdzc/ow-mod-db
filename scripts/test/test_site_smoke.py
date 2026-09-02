"""构建产物冒烟测试: 跑 build 后检查 dist 产物结构。"""
import json
from pathlib import Path

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
    meta = {"generatedAt": "2026-09-02T00:00:00Z", "mods": len(mods_data), "zhDescriptions": 1}
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
                     "latestReleaseDescription"}
    for mod in mods:
        assert set(mod.keys()) == required_keys


def test_mirror_pages_cover_three_views():
    index = (REPO_ROOT / "site" / "index.html").read_text(encoding="utf-8")
    mods = (REPO_ROOT / "site" / "mods.html").read_text(encoding="utf-8")
    assert "featured" in index   # 首页三栏
    assert "mod-grid" in mods    # 列表页网格
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert "uniqueName" in js    # 详情页从 URL 参数读 uniqueName
