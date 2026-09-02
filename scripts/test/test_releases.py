import json

import releases


def test_normalize_picks_zip_and_trims():
    payload = [
        {"tag_name": "v1.0", "name": "1.0", "published_at": "2026-01-02T00:00:00Z",
         "body": "说明" * 3000,
         "assets": [
             {"browser_download_url": "https://x/Mod.zip"},
             {"browser_download_url": "https://x/Mod.pdb"},
         ]},
    ]
    out = releases.normalize_releases(payload, "owner/repo")
    assert len(out) == 1
    assert out[0]["tag"] == "v1.0"
    assert out[0]["zipUrl"] == "https://x/Mod.zip"
    assert out[0]["date"] == "2026-01-02"
    assert len(out[0]["body"]) <= releases.MAX_BODY_CHARS
    assert out[0]["releaseUrl"] == "https://github.com/owner/repo/releases/tag/v1.0"


def test_normalize_caps_count_and_no_zip_fallback():
    payload = [{"tag_name": f"v{i}", "name": "", "published_at": "", "body": "",
                "assets": []} for i in range(20)]
    out = releases.normalize_releases(payload, "o/r")
    assert len(out) == releases.MAX_RELEASES
    assert out[0]["zipUrl"] == ""
    assert out[0]["releaseUrl"].startswith("https://github.com/o/r/releases/tag/")


def _body_cache():
    def rel(tag, body, zh=""):
        return {"tag": tag, "name": tag, "date": "2026-01-01", "body": body,
                "bodyZh": zh, "zipUrl": "", "releaseUrl": ""}
    return {
        "Lic.Mit": {"repoUpdatedAt": "t", "releases": [
            rel("v1", "Release one."), rel("v0", "Older note.")]},
        "Lic.None": {"repoUpdatedAt": "t", "releases": [rel("v1", "No license note.")]},
    }


def test_translate_bodies_only_permissive_and_fills_zh():
    cache = _body_cache()
    licenses = {"Lic.Mit": "MIT", "Lic.None": "none"}
    calls = []

    def fake_ai(text):
        calls.append(text)
        return "译:" + text

    new, errors = releases.translate_bodies(cache, licenses, [], {}, fake_ai)
    assert new == 2
    assert errors == []
    assert cache["Lic.Mit"]["releases"][0]["bodyZh"].startswith("译:")
    assert cache["Lic.Mit"]["releases"][1]["bodyZh"].startswith("译:")
    assert cache["Lic.None"]["releases"][0]["bodyZh"] == ""  # 无许可不动


def test_translate_bodies_skips_existing_and_denylist():
    cache = _body_cache()
    cache["Lic.Mit"]["releases"][0]["bodyZh"] = "已有"
    licenses = {"Lic.Mit": "MIT", "Lic.None": "none"}
    calls = []
    new, _ = releases.translate_bodies(cache, licenses, ["Lic.Mit"], {},
                                       lambda t: calls.append(t) or "译")
    assert new == 0  # 第一条已有,第二条因 denylist 整个跳过


def test_refresh_skips_unchanged_repoUpdatedAt():
    official = {"releases": [{"uniqueName": "A.B", "repo": "https://github.com/x/y",
                              "repoUpdatedAt": "t1"}]}
    cache = {"A.B": {"repoUpdatedAt": "t1", "releases": [{"tag": "v1"}]}}
    updated, skipped, errors = releases.refresh_cache(official, cache, "")
    assert updated == 0 and skipped == 0 and errors == []
    assert cache["A.B"]["releases"][0]["tag"] == "v1"  # 缓存未被触碰
