import json
from pathlib import Path

import pytest

import build
from translation_store import load_json

FIXTURE = Path(__file__).parent / "fixtures" / "official.json"


def _official() -> dict:
    return load_json(FIXTURE)


def _translations() -> dict:
    return {
        "Alek.OWML": {
            "name": {"en": "OWML", "zh": "OWML", "at": "t"},
            "description": {"en": "The mod loader and mod framework for Outer Wilds",
                            "zh": "OWML 的模组加载器", "at": "t"},
        },
        "Test.Mod": {
            "description": {"en": "A test mod description", "zh": "测试模组简介", "at": "t"},
            "latestReleaseDescription": {"en": "Fixed a bug", "zh": "修复了一个 Bug", "at": "t"},
        },
    }


def test_translate_mod_replaces_only_translated_fields():
    mod = {"uniqueName": "Test.Mod", "name": "Test Mod", "description": "A test mod description",
           "author": "tester", "latestReleaseDescription": "Fixed a bug", "tags": ["gameplay"]}
    out = build.translate_mod(mod, _translations())
    assert out["name"] == "Test Mod"          # 无译文 → 保留英文
    assert out["description"] == "测试模组简介"
    assert out["latestReleaseDescription"] == "修复了一个 Bug"
    assert out["author"] == "tester"          # 非翻译字段原样
    assert out["tags"] == ["gameplay"]


def test_build_all_structure_matches_official():
    official = _official()
    database, mods_data = build.build_all(official, _translations())
    assert set(database.keys()) == set(official.keys())
    assert len(database["releases"]) == len(official["releases"])
    assert len(database["alphaReleases"]) == len(official["alphaReleases"])
    # 每个 mod 字段与官方一致(仅三个翻译字段可能不同)
    for group in ("releases", "alphaReleases"):
        for out_mod, src_mod in zip(database[group], official[group]):
            assert set(out_mod.keys()) == set(src_mod.keys())
            for key, value in src_mod.items():
                if key not in build.TRANSLATABLE_FIELDS:
                    assert out_mod[key] == value, f"{key} 不应被改动"


def test_build_all_produces_site_data_from_releases():
    database, mods_data = build.build_all(_official(), _translations())
    assert len(mods_data) == 2  # 只含 releases
    by_name = {m["uniqueName"]: m for m in mods_data}
    assert by_name["Alek.OWML"]["description"] == "OWML 的模组加载器"
    assert by_name["Test.Mod"]["name"] == "Test Mod"  # 无译文保留英文
    assert by_name["Test.Mod"]["latestReleaseDate"] == ""  # 字段存在
    assert "authorDisplay" in by_name["Alek.OWML"]


def test_site_data_normalizes_version_and_author():
    database, mods_data = build.build_all(_official(), _translations())
    by_name = {m["uniqueName"]: m for m in mods_data}
    # Test.Mod: 无 authorDisplay → 回退 author; version 去除前导 v
    assert by_name["Test.Mod"]["authorDisplay"] == "tester"
    assert by_name["Test.Mod"]["version"] == "1.5.1"
    # database.json 保持官方原样(v 前缀与缺失字段不动)
    src = next(m for m in _official()["releases"] if m["uniqueName"] == "Test.Mod")
    out = next(m for m in database["releases"] if m["uniqueName"] == "Test.Mod")
    assert out["version"] == src["version"] == "v1.5.1"
    assert "authorDisplay" not in out and "authorDisplay" not in src


def test_site_data_has_exact_key_set():
    _, mods_data = build.build_all(_official(), _translations())
    expected = {"uniqueName", "name", "description", "authorDisplay", "downloadUrl",
                "repo", "tags", "slug", "thumbnail", "downloadCount", "installCount",
                "weeklyInstallCount", "version", "latestReleaseDate", "firstReleaseDate",
                "latestReleaseDescription", "readmeDownloadUrl", "parent", "repoVariations"}
    for mod in mods_data:
        assert set(mod.keys()) == expected


def test_deploy_site_copies_files(tmp_path):
    site = tmp_path / "site"
    (site / "css").mkdir(parents=True)
    (site / "index.html").write_text("<html></html>", encoding="utf-8")
    (site / "css" / "style.css").write_text("body {}", encoding="utf-8")
    dist = tmp_path / "dist"
    build.deploy_site(site, dist)
    assert (dist / "index.html").exists()
    assert (dist / "css" / "style.css").read_text(encoding="utf-8") == "body {}"


def test_meta_with_lang_marks_language_and_counts_cjk():
    _, zh_mods = build.build_all(_official(), _translations())
    zh_meta = build.meta_with_lang("zh_cn", zh_mods, "2026-09-03T00:00:00Z")
    assert zh_meta["lang"] == "zh_cn"
    assert zh_meta["mods"] == 2
    assert zh_meta["zhDescriptions"] == 2          # 两个 mod 简介均有译文
    _, en_mods = build.build_all(_official(), {})  # en = 无翻译
    en_meta = build.meta_with_lang("en", en_mods, "2026-09-03T00:00:00Z")
    assert en_meta["lang"] == "en"
    assert en_meta["zhDescriptions"] == 0          # 官方原文不含中文
