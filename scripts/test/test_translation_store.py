import json
from pathlib import Path

import pytest

from translation_store import (
    LANG_DEFAULT,
    TRANSLATABLE_FIELDS,
    StoreError,
    get_translation,
    lang_file,
    load_json,
    load_list,
    needs_translation,
    save_json,
    save_list,
    set_translation,
    site_data_dir,
)


def test_translatable_fields_are_the_three_expected():
    assert TRANSLATABLE_FIELDS == ("name", "description", "latestReleaseDescription")


def test_load_missing_file_returns_empty(tmp_path):
    assert load_json(tmp_path / "nope.json") == {}
    assert load_list(tmp_path / "nope.json") == []


def test_load_invalid_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(StoreError):
        load_json(bad)


def test_load_wrong_type_raises(tmp_path):
    arr = tmp_path / "arr.json"
    arr.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(StoreError):
        load_json(arr)


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "data.json"
    save_json(path, {"a": "中文字符"})
    assert load_json(path) == {"a": "中文字符"}
    assert "中文字符" in path.read_text(encoding="utf-8")  # ensure_ascii=False


def test_save_load_list_roundtrip(tmp_path):
    path = tmp_path / "pending.json"
    save_list(path, [{"unique_name": "X", "field": "name"}])
    assert load_list(path) == [{"unique_name": "X", "field": "name"}]


def test_needs_translation_new_field():
    assert needs_translation({}, "Mod.A", "description", "Hello")


def test_needs_translation_skips_empty_text():
    assert not needs_translation({}, "Mod.A", "description", "")
    assert not needs_translation({}, "Mod.A", "description", "   ")


def test_needs_translation_unchanged_is_false():
    translations = {"Mod.A": {"name": {"en": "Same", "zh": "相同", "at": "t"}}}
    assert not needs_translation(translations, "Mod.A", "name", "Same")


def test_needs_translation_changed_is_true():
    translations = {"Mod.A": {"name": {"en": "Old", "zh": "旧", "at": "t"}}}
    assert needs_translation(translations, "Mod.A", "name", "New")


def test_set_and_get_translation():
    translations = {}
    set_translation(translations, "Mod.A", "description", "En text", "中译", "2026-09-02T00:00:00Z")
    assert translations["Mod.A"]["description"] == {
        "en": "En text", "zh": "中译", "at": "2026-09-02T00:00:00Z",
    }
    assert get_translation(translations, "Mod.A", "description") == "中译"
    assert get_translation(translations, "Mod.A", "name") is None
    assert get_translation(translations, "NoSuch", "description") is None


def test_lang_file_paths():
    assert str(lang_file("glossary")) == "source/zh_cn/glossary.json"
    assert str(lang_file("translations", "ja")) == "source/ja/translations.json"
    assert LANG_DEFAULT == "zh_cn"


def test_site_data_dir():
    assert site_data_dir("zh_cn") == "data"
    assert site_data_dir("ja") == "data/ja"
