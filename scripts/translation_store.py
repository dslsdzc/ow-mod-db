"""Shared JSON storage helpers and translation cache logic."""

import json
from pathlib import Path

TRANSLATABLE_FIELDS = ("name", "description", "latestReleaseDescription")


class StoreError(Exception):
    pass


def _read(path: Path) -> object:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = _read(path)
    except json.JSONDecodeError as e:
        raise StoreError(f"invalid JSON in {path}: {e}") from e
    if not isinstance(data, dict):
        raise StoreError(f"{path} must contain a JSON object")
    return data


def load_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        data = _read(path)
    except json.JSONDecodeError as e:
        raise StoreError(f"invalid JSON in {path}: {e}") from e
    if not isinstance(data, list):
        raise StoreError(f"{path} must contain a JSON array")
    return data


def save_json(path: Path, data: dict) -> None:
    _write(path, data)


def save_list(path: Path, data: list) -> None:
    _write(path, data)


def load_translations(path: Path) -> dict:
    """Returns {unique_name: {field: {"en": str, "zh": str, "at": str}}}."""
    return load_json(path)


def needs_translation(translations: dict, unique_name: str, field: str, en_text: str) -> bool:
    if not en_text or not en_text.strip():
        return False
    cached = translations.get(unique_name, {}).get(field)
    return cached is None or cached.get("en") != en_text


def set_translation(translations: dict, unique_name: str, field: str, en_text: str, zh_text: str, at: str) -> None:
    entry = translations.setdefault(unique_name, {})
    entry[field] = {"en": en_text, "zh": zh_text, "at": at}


def get_translation(translations: dict, unique_name: str, field: str) -> str | None:
    cached = translations.get(unique_name, {}).get(field)
    if cached is None:
        return None
    return cached.get("zh")


LANG_DEFAULT = "zh_cn"


def lang_file(kind: str, lang: str = LANG_DEFAULT) -> Path:
    """语言化 JSON 的路径: source/<lang>/<kind>.json"""
    return Path("source") / lang / f"{kind}.json"


def site_data_dir(lang: str) -> str:
    """网站数据目录: zh_cn 用根 data/,其它语言 data/<code>/"""
    return "data" if lang == "zh_cn" else f"data/{lang}"
