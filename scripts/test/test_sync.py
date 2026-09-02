import json
from pathlib import Path

import pytest

import sync
from translation_store import load_json


FIXTURE = Path(__file__).parent / "fixtures" / "official.json"


def _official() -> dict:
    return load_json(FIXTURE)


def test_diff_finds_everything_when_cache_empty():
    pending = sync.diff_database(_official(), {})
    fields = {(p["unique_name"], p["field"]) for p in pending}
    assert fields == {
        ("Alek.OWML", "name"),
        ("Alek.OWML", "description"),
        ("Test.Mod", "name"),
        ("Test.Mod", "description"),
        ("Test.Mod", "latestReleaseDescription"),
        ("Test.Alpha", "name"),
        ("Test.Alpha", "description"),
    }


def test_diff_skips_unchanged_and_empty():
    translations = {
        "Alek.OWML": {
            "name": {"en": "OWML", "zh": "OWML", "at": "t"},
            "description": {"en": "The mod loader and mod framework for Outer Wilds", "zh": "…", "at": "t"},
        },
    }
    pending = sync.diff_database(_official(), translations)
    fields = {(p["unique_name"], p["field"]) for p in pending}
    assert ("Alek.OWML", "name") not in fields          # 未变化
    assert ("Alek.OWML", "description") not in fields   # 未变化
    assert ("Test.Mod", "latestReleaseDescription") in fields
    assert ("Alek.OWML", "latestReleaseDescription") not in fields  # 空字段跳过
    assert all(p["en"] for p in pending)


def test_diff_detects_changed_field():
    translations = {"Test.Mod": {"name": {"en": "Old Name", "zh": "旧", "at": "t"}}}
    pending = sync.diff_database(_official(), translations)
    changed = [p for p in pending if p["unique_name"] == "Test.Mod" and p["field"] == "name"]
    assert changed == [{"unique_name": "Test.Mod", "field": "name", "en": "Test Mod"}]


def test_fetch_official_raises_on_bad_format(monkeypatch):
    class BadResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {"not": "the db"}

    def fake_get(url, timeout=None, follow_redirects=None):
        return BadResp()

    monkeypatch.setattr(sync.httpx, "get", fake_get)
    with pytest.raises(ValueError, match="unexpected official database format"):
        sync.fetch_official("https://example.com/db.json")


def test_main_writes_pending_and_snapshot(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_fetch(url):
        calls["n"] += 1
        return _official()

    monkeypatch.setattr(sync, "fetch_official", fake_fetch)
    out = tmp_path / "pending.json"
    snapshot = tmp_path / "official.json"
    monkeypatch.setattr(
        "sys.argv",
        ["sync.py", "--official", "https://example.com/db.json",
         "--out", str(out), "--save-official", str(snapshot),
         "--translations", str(tmp_path / "translations.json")],
    )
    sync.main()

    assert calls["n"] == 1
    pending = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(pending, list) and len(pending) == 7
    assert json.loads(snapshot.read_text(encoding="utf-8")) == _official()
