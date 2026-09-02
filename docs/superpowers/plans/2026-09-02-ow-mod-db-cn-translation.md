# 星际拓荒 MOD 数据库汉化流水线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一条全自动流水线:定时同步官方 Outer Wilds MOD 数据库,用 AI API 汉化 `name`/`description`/`latestReleaseDescription`,产出中文 `database.json`(OWMM 可替换)与中文网站(GitHub Pages),并支持术语表与人工翻译覆盖。

**Architecture:** 单仓库双分支。`main` 存源码与翻译缓存(`source/`),GitHub Actions 每 6 小时运行 `sync.py → translate.py → build.py`,产物写入 `dist/` 并部署到 `gh-pages` 分支。翻译优先级:人工覆盖 `human_translations.json` > AI(带术语表 `glossary.json`)。只翻译有变化的字段(增量),省 API 费用。

**Tech Stack:** Python 3.11 + httpx + pytest;原生 HTML/CSS/JS 静态网站(客户端渲染);GitHub Actions + peaceiris/actions-gh-pages。

## Global Constraints

- Python 3.11+,依赖仅 `httpx` 和 `pytest`(`requirements.txt`)
- 翻译字段仅 `name`、`description`、`latestReleaseDescription`;`author` 等其余字段**原样保留**
- 输出 `database.json` 结构必须与官方完全一致(字段齐全,仅替换三个翻译字段)
- 空字段不翻译;AI 失败重试 3 次(2s/4s/8s 退避)后跳过该条并记入失败列表,不阻塞发布
- 密钥只在 CI 环境变量中(`OPENAI_BASE_URL`/`OPENAI_API_KEY`/`OPENAI_MODEL`),产物不含密钥
- 所有脚本从仓库根目录运行;测试文件放 `scripts/test/`,统一从根目录执行 `python -m pytest scripts/test -q`

---

### Task 1: 脚手架与共享存储模块 translation_store

**Files:**
- Create: `requirements.txt`
- Create: `source/glossary.json`
- Create: `source/human_translations.json`
- Create: `source/translations.json`
- Create: `scripts/translation_store.py`
- Create: `scripts/test/conftest.py`
- Create: `scripts/test/test_translation_store.py`

**Interfaces:**
- Produces(后续所有任务依赖):
  - `TRANSLATABLE_FIELDS: tuple[str, ...]` = `("name", "description", "latestReleaseDescription")`
  - `class StoreError(Exception)`
  - `load_json(path: Path) -> dict`
  - `load_list(path: Path) -> list`
  - `save_json(path: Path, data: dict) -> None`(写入 `path.with_suffix(".tmp")` 后原子替换)
  - `save_list(path: Path, data: list) -> None`
  - `load_translations(path: Path) -> dict`(缓存格式见下)
  - `needs_translation(translations: dict, unique_name: str, field: str, en_text: str) -> bool`
  - `set_translation(translations: dict, unique_name: str, field: str, en_text: str, zh_text: str, at: str) -> None`
  - `get_translation(translations: dict, unique_name: str, field: str) -> str | None`

**翻译缓存格式**(`translations.json`):
```json
{
  "Alek.OWML": {
    "description": {"en": "The mod loader...", "zh": "…", "at": "2026-09-02T12:00:00Z"}
  }
}
```

- [ ] **Step 1: 创建基础文件**

`requirements.txt`:
```
httpx>=0.27
pytest>=8
```

`source/glossary.json`(种子术语表,官方中文版用词;团队后续随时扩充):
```json
{
  "Outer Wilds": "星际拓荒",
  "Nomai": "挪麦",
  "Hearthian": "哈斯人",
  "Timber Hearth": "木炉星",
  "Quantum Moon": "量子之月",
  "The Eye of the Universe": "宇宙之眼",
  "Dark Bramble": "暗棘星",
  "Brittle Hollow": "碎空星",
  "Giant's Deep": "巨人之深",
  "Ash Twin": "灰烬双星",
  "OWML": "OWML",
  "Outer Wilds Mod Manager": "星际拓荒模组管理器"
}
```

`source/human_translations.json`:
```json
{}
```

`source/translations.json`:
```json
{}
```

- [ ] **Step 2: 写失败测试**

`scripts/test/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

`scripts/test/test_translation_store.py`:
```python
import json
from pathlib import Path

import pytest

from translation_store import (
    TRANSLATABLE_FIELDS,
    StoreError,
    get_translation,
    load_json,
    load_list,
    needs_translation,
    save_json,
    save_list,
    set_translation,
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
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest scripts/test/test_translation_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'translation_store'`

- [ ] **Step 4: 实现 translation_store.py**

`scripts/translation_store.py`:
```python
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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest scripts/test/test_translation_store.py -q`
Expected: 9 passed

- [ ] **Step 6: 提交**

```bash
git add requirements.txt source/ scripts/
git commit -m "feat: 翻译缓存存储模块与项目脚手架"
```

---

### Task 2: AI 客户端 ai_client

**Files:**
- Create: `scripts/ai_client.py`
- Create: `scripts/test/test_ai_client.py`

**Interfaces:**
- Consumes: 无(独立;仅依赖 httpx)
- Produces:
  - `class AIError(Exception)`
  - `translate_with_ai(en_text: str, glossary: dict[str, str], *, base_url: str, api_key: str, model: str) -> str` — 返回中文译文,失败抛 `AIError`

**调用约定:** POST `{base_url}/chat/completions`,Bearer 认证,system prompt 含术语表,`temperature: 0.2`。

- [ ] **Step 1: 写失败测试**

`scripts/test/test_ai_client.py`(monkeypatch 模块级 `httpx.post`,不依赖网络):
```python
import httpx
import pytest

import ai_client
from ai_client import AIError


class FakePost:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.calls: list[tuple[str, dict, dict]] = []

    def __call__(self, url, *, json=None, headers=None, timeout=None):
        self.calls.append((url, json, headers))
        return self.response


def test_translate_success(monkeypatch):
    fake = FakePost(httpx.Response(200, json={"choices": [{"message": {"content": " 中译结果 "}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)

    result = ai_client.translate_with_ai(
        "The mod loader for Outer Wilds",
        {"Nomai": "挪麦"},
        base_url="https://api.example.com/",
        api_key="secret-key",
        model="deepseek-chat",
    )
    assert result == "中译结果"

    url, payload, headers = fake.calls[0]
    assert url == "https://api.example.com/chat/completions"
    assert headers["Authorization"] == "Bearer secret-key"
    assert payload["model"] == "deepseek-chat"
    assert payload["temperature"] == 0.2
    system = payload["messages"][0]["content"]
    assert "Nomai -> 挪麦" in system
    assert "The mod loader for Outer Wilds" in payload["messages"][1]["content"]


def test_translate_strips_whitespace(monkeypatch):
    fake = FakePost(httpx.Response(200, json={"choices": [{"message": {"content": "译文\n"}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    assert ai_client.translate_with_ai("Hi", {}, base_url="u", api_key="k", model="m") == "译文"


def test_translate_non_200_raises(monkeypatch):
    fake = FakePost(httpx.Response(500, text="boom"))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    with pytest.raises(AIError, match="500"):
        ai_client.translate_with_ai("Hi", {}, base_url="u", api_key="k", model="m")


def test_translate_network_error_raises(monkeypatch):
    def boom(*a, **kw):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(ai_client.httpx, "post", boom)
    with pytest.raises(AIError, match="request failed"):
        ai_client.translate_with_ai("Hi", {}, base_url="u", api_key="k", model="m")


def test_translate_bad_shape_raises(monkeypatch):
    fake = FakePost(httpx.Response(200, json={"unexpected": True}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    with pytest.raises(AIError, match="unexpected API response"):
        ai_client.translate_with_ai("Hi", {}, base_url="u", api_key="k", model="m")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest scripts/test/test_ai_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_client'`

- [ ] **Step 3: 实现 ai_client.py**

`scripts/ai_client.py`:
```python
"""OpenAI-compatible chat-completions client for translation."""

import httpx

SYSTEM_PROMPT = (
    "You are a professional game mod localization translator. "
    "Translate English Outer Wilds mod metadata to Simplified Chinese.\n"
    "Rules:\n"
    "1. Proper nouns must use the glossary mapping exactly. "
    "Proper nouns not in the glossary stay in English.\n"
    "2. Keep Markdown formatting, line breaks, URLs, and angle brackets intact.\n"
    "3. Output only the translation, no quotes, no explanation.\n"
    "Glossary:\n{glossary}"
)


class AIError(Exception):
    pass


def _glossary_block(glossary: dict) -> str:
    if not glossary:
        return "(empty)"
    return "\n".join(f"{en} -> {zh}" for en, zh in glossary.items())


def translate_with_ai(en_text: str, glossary: dict, *, base_url: str, api_key: str, model: str) -> str:
    """Translate a single English text via an OpenAI-compatible chat API.

    Returns the translated text (stripped). Raises AIError on any failure.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(glossary=_glossary_block(glossary))},
            {
                "role": "user",
                "content": "Translate the following text to Simplified Chinese.\nText:\n" + en_text,
            },
        ],
        "temperature": 0.2,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=60.0)
    except httpx.HTTPError as e:
        raise AIError(f"request failed: {e}") from e
    if resp.status_code != 200:
        raise AIError(f"API returned {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        raise AIError(f"unexpected API response: {e}") from e
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest scripts/test/test_ai_client.py -q`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add scripts/ai_client.py scripts/test/test_ai_client.py
git commit -m "feat: OpenAI 兼容 AI 翻译客户端"
```

---

### Task 3: 同步与差异检测 sync

**Files:**
- Create: `scripts/sync.py`
- Create: `scripts/test/test_sync.py`
- Create: `scripts/test/fixtures/official.json`

**Interfaces:**
- Consumes: `translation_store`(load_json / load_translations / save_json / save_list / TRANSLATABLE_FIELDS / needs_translation)
- Produces:
  - `fetch_official(url: str = OFFICIAL_DB_URL) -> dict` — 下载官方库(URL 或本地路径由 main 处理)
  - `diff_database(official: dict, translations: dict) -> list[dict]` — 返回 `[{"unique_name", "field", "en"}]`
  - CLI: `python scripts/sync.py [--official URL|path] [--translations PATH] [--out PATH] [--save-official PATH]`
  - 默认: 下载官方库 → 写 `source/pending.json`(待翻译清单)+ `source/official.json`(快照,供 build)

- [ ] **Step 1: 写失败测试**

`scripts/test/fixtures/official.json`:
```json
{
  "modManager": {"version": "v1.18.0"},
  "releases": [
    {
      "uniqueName": "Alek.OWML",
      "name": "OWML",
      "description": "The mod loader and mod framework for Outer Wilds",
      "author": "ow-mods",
      "latestReleaseDescription": "",
      "tags": ["library"]
    },
    {
      "uniqueName": "Test.Mod",
      "name": "Test Mod",
      "description": "A test mod description",
      "author": "tester",
      "latestReleaseDescription": "Fixed a bug",
      "tags": ["gameplay"]
    }
  ],
  "alphaReleases": [
    {
      "uniqueName": "Test.Alpha",
      "name": "Alpha Mod",
      "description": "Alpha description",
      "author": "tester",
      "latestReleaseDescription": ""
    }
  ]
}
```

`scripts/test/test_sync.py`:
```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest scripts/test/test_sync.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync'`

- [ ] **Step 3: 实现 sync.py**

`scripts/sync.py`:
```python
"""Sync official database and compute translation diffs."""

import argparse
from pathlib import Path

import httpx

from translation_store import (
    TRANSLATABLE_FIELDS,
    load_json,
    load_translations,
    needs_translation,
    save_json,
    save_list,
)

OFFICIAL_DB_URL = "https://ow-mods.github.io/ow-mod-db/database.json"


def fetch_official(url: str = OFFICIAL_DB_URL) -> dict:
    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict) or "releases" not in data:
        raise ValueError("unexpected official database format")
    return data


def diff_database(official: dict, translations: dict) -> list[dict]:
    """Return [{unique_name, field, en}] for fields that changed or are new."""
    pending = []
    for group in ("releases", "alphaReleases"):
        for mod in official.get(group, []):
            unique_name = mod.get("uniqueName")
            if not unique_name:
                continue
            for field in TRANSLATABLE_FIELDS:
                en_text = mod.get(field) or ""
                if needs_translation(translations, unique_name, field, en_text):
                    pending.append({"unique_name": unique_name, "field": field, "en": en_text})
    return pending


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync official db and write pending translations")
    parser.add_argument("--official", default=OFFICIAL_DB_URL, help="official database.json URL or local path")
    parser.add_argument("--translations", default="source/translations.json")
    parser.add_argument("--out", default="source/pending.json")
    parser.add_argument("--save-official", default="source/official.json", help="snapshot for build.py")
    args = parser.parse_args()

    if args.official.startswith("http"):
        official = fetch_official(args.official)
    else:
        official = load_json(Path(args.official))

    translations = load_translations(Path(args.translations))
    pending = diff_database(official, translations)
    save_list(Path(args.out), pending)
    save_json(Path(args.save_official), official)
    print(f"{len(pending)} pending translations")
    for item in pending[:5]:
        print(f"  {item['unique_name']}.{item['field']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest scripts/test/test_sync.py -q`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add scripts/sync.py scripts/test/test_sync.py scripts/test/fixtures/
git commit -m "feat: 官方数据库同步与差异检测"
```

---

### Task 4: 翻译器 translate

**Files:**
- Create: `scripts/translate.py`
- Create: `scripts/test/test_translate.py`

**Interfaces:**
- Consumes: `ai_client.translate_with_ai`、`ai_client.AIError`、`translation_store`(load_json / load_list / load_translations / save_json / set_translation)
- Produces:
  - `_human_get(human: dict, unique_name: str, field: str) -> str | None`
  - `translate_pending(pending: list[dict], translations: dict, human: dict, glossary: dict, ai_translate, *, at: str, max_retries: int = 3, backoff_s: float = 2.0, sleep=time.sleep) -> tuple[int, list[str]]` — `ai_translate` 是可注入的 `(en_text: str, glossary: dict) -> str`;返回 `(成功条数, 失败描述列表)`,失败条目不写缓存(保持英文)
  - CLI: `python scripts/translate.py [--pending PATH] [--translations PATH] [--human PATH] [--glossary PATH] [--dry-run] [--at ISO]`
  - 非 dry-run 时必须存在环境变量 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL`

- [ ] **Step 1: 写失败测试**

`scripts/test/test_translate.py`:
```python
import json
from pathlib import Path

import pytest

import translate
from ai_client import AIError
from translation_store import load_json, load_list


class FakeAI:
    """可编程的 AI 翻译替身: (en_text, glossary) -> zh;记录调用。"""

    def __init__(self, mapping=None, failures=0):
        self.mapping = mapping or {}
        self.failures = failures
        self.calls = []

    def __call__(self, en_text, glossary):
        self.calls.append((en_text, glossary))
        if self.failures > 0:
            self.failures -= 1
            raise AIError("transient")
        return self.mapping.get(en_text, "自动译:" + en_text)


def _pending():
    return [
        {"unique_name": "Test.Mod", "field": "description", "en": "English text"},
        {"unique_name": "Test.Mod", "field": "name", "en": "Test Mod"},
        {"unique_name": "Test.Alpha", "field": "description", "en": "Alpha text"},
    ]


def test_human_override_beats_ai():
    human = {"Test.Mod": {"description": "人工精校版"}}
    translations = {}
    fake = FakeAI()
    translated, failures = translate.translate_pending(
        _pending(), translations, human, {}, fake, at="2026-09-02T00:00:00Z"
    )
    assert translated == 3
    assert failures == []
    assert translations["Test.Mod"]["description"]["zh"] == "人工精校版"
    assert fake.calls == [("Test Mod", {}), ("Alpha text", {})]  # 人工覆盖未调 AI


def test_ai_result_stored_with_en_zh_at():
    translations = {}
    fake = FakeAI()
    translate.translate_pending(_pending(), translations, {}, {"Nomai": "挪麦"}, fake,
                                at="2026-09-02T00:00:00Z")
    entry = translations["Test.Mod"]["description"]
    assert entry == {"en": "English text", "zh": "自动译:English text", "at": "2026-09-02T00:00:00Z"}
    # glossary 传给 AI
    assert fake.calls[0][1] == {"Nomai": "挪麦"}


def test_failure_skips_item_keeps_english_and_reports():
    translations = {}
    fake = FakeAI(failures=99)  # 永远失败
    no_sleep = lambda _s: None
    translated, failures = translate.translate_pending(
        _pending(), translations, {}, {}, fake, at="t", sleep=no_sleep
    )
    assert translated == 0
    assert len(failures) == 3
    assert translations == {}  # 失败不写缓存,保持英文


def test_retries_then_succeeds():
    translations = {}
    fake = FakeAI(failures=2)  # 前两次失败,第三次成功
    no_sleep = lambda _s: None
    translated, failures = translate.translate_pending(
        _pending()[:1], translations, {}, {}, fake, at="t", sleep=no_sleep
    )
    assert translated == 1
    assert failures == []
    assert len(fake.calls) == 3
    assert translations["Test.Mod"]["description"]["zh"] == "自动译:English text"


def test_main_dry_run_calls_no_ai(tmp_path, monkeypatch):
    out = tmp_path / "translations.json"
    out.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "translate.py", "--pending", "NONEXISTENT", "--dry-run",
        "--translations", str(out), "--human", str(tmp_path / "h.json"),
        "--glossary", str(tmp_path / "g.json"),
    ])

    def boom(*a, **kw):
        raise AssertionError("dry-run 不应调用 AI")

    monkeypatch.setattr(translate.ai_client, "translate_with_ai", boom)
    translate.main()  # 不应抛错
    assert json.loads(out.read_text(encoding="utf-8")) == {}  # 缓存未变
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest scripts/test/test_translate.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'translate'`

- [ ] **Step 3: 实现 translate.py**

`scripts/translate.py`:
```python
"""Translate pending fields: human overrides first, then AI with glossary."""

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import ai_client
from translation_store import (
    load_json,
    load_list,
    load_translations,
    save_json,
    set_translation,
)


def _human_get(human: dict, unique_name: str, field: str) -> str | None:
    entry = human.get(unique_name)
    if isinstance(entry, dict):
        value = entry.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _call_with_retries(ai_translate, en_text: str, glossary: dict, max_retries: int,
                       backoff_s: float, sleep) -> str:
    last_error = None
    for attempt in range(max_retries):
        try:
            return ai_translate(en_text, glossary)
        except ai_client.AIError as e:
            last_error = e
            sleep(backoff_s * (2 ** attempt))
    raise ai_client.AIError(f"failed after {max_retries} retries: {last_error}")


def translate_pending(pending: list[dict], translations: dict, human: dict, glossary: dict,
                      ai_translate, *, at: str, max_retries: int = 3, backoff_s: float = 2.0,
                      sleep=time.sleep) -> tuple[int, list[str]]:
    """Translate each pending item. Returns (translated_count, failure_messages).

    Failed items are left untranslated (English kept) and reported, not fatal.
    """
    translated = 0
    failures = []
    for item in pending:
        unique_name, field, en_text = item["unique_name"], item["field"], item["en"]
        human_zh = _human_get(human, unique_name, field)
        if human_zh is not None:
            set_translation(translations, unique_name, field, en_text, human_zh, at)
            translated += 1
            continue
        try:
            zh = _call_with_retries(ai_translate, en_text, glossary, max_retries, backoff_s, sleep)
        except ai_client.AIError as e:
            failures.append(f"{unique_name}.{field}: {e}")
            continue
        set_translation(translations, unique_name, field, en_text, zh, at)
        translated += 1
    return translated, failures


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate pending fields into translations.json")
    parser.add_argument("--pending", default="source/pending.json")
    parser.add_argument("--translations", default="source/translations.json")
    parser.add_argument("--human", default="source/human_translations.json")
    parser.add_argument("--glossary", default="source/glossary.json")
    parser.add_argument("--dry-run", action="store_true", help="只输出统计,不调用 AI")
    parser.add_argument("--at", default=None, help="ISO 时间戳,默认当前 UTC")
    args = parser.parse_args()

    pending = load_list(Path(args.pending))
    translations = load_translations(Path(args.translations))
    human = load_json(Path(args.human))
    glossary = load_json(Path(args.glossary))
    at = args.at or _now_iso()

    if args.dry_run:
        print(f"[dry-run] {len(pending)} 条待翻译,跳过 AI 调用")
        return

    def ai_translate(en_text: str, glossary: dict) -> str:
        return ai_client.translate_with_ai(
            en_text, glossary,
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["OPENAI_API_KEY"],
            model=os.environ["OPENAI_MODEL"],
        )

    translated, failures = translate_pending(
        pending, translations, human, glossary, ai_translate, at=at
    )
    save_json(Path(args.translations), translations)
    print(f"翻译完成: {translated} 条成功, {len(failures)} 条失败")
    for f in failures:
        print(f"  FAIL {f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest scripts/test/test_translate.py -q`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add scripts/translate.py scripts/test/test_translate.py
git commit -m "feat: AI 翻译器(人工覆盖优先、重试、dry-run)"
```

---

### Task 5: 生成器 build

**Files:**
- Create: `scripts/build.py`
- Create: `scripts/test/test_build.py`

**Interfaces:**
- Consumes: `translation_store`(TRANSLATABLE_FIELDS / load_json / load_translations / get_translation)
- Produces:
  - `translate_mod(mod: dict, translations: dict) -> dict` — 原字典拷贝,三个字段有译文则替换,其余字段原样
  - `build_all(official: dict, translations: dict) -> tuple[dict, list[dict]]` — `(中文 database.json, 网站 mods 数据列表)`
  - `deploy_site(site_dir: Path, dist_dir: Path) -> None` — 复制 `site/` 全部文件到 `dist/`
  - CLI: `python scripts/build.py [--official PATH] [--translations PATH] [--site PATH] [--dist PATH]`
  - 默认产物: `dist/database.json`、`dist/data/mods.json`、`dist/` 下网站文件

- [ ] **Step 1: 写失败测试**

`scripts/test/test_build.py`:
```python
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


def test_deploy_site_copies_files(tmp_path):
    site = tmp_path / "site"
    (site / "css").mkdir(parents=True)
    (site / "index.html").write_text("<html></html>", encoding="utf-8")
    (site / "css" / "style.css").write_text("body {}", encoding="utf-8")
    dist = tmp_path / "dist"
    build.deploy_site(site, dist)
    assert (dist / "index.html").exists()
    assert (dist / "css" / "style.css").read_text(encoding="utf-8") == "body {}"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest scripts/test/test_build.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'build'`

- [ ] **Step 3: 实现 build.py**

`scripts/build.py`:
```python
"""Merge official db + translations into Chinese database.json and site data."""

import argparse
import shutil
from pathlib import Path

from translation_store import (
    TRANSLATABLE_FIELDS,
    get_translation,
    load_json,
    load_translations,
    save_json,
)

SITE_SOURCE = Path("site")
DIST = Path("dist")


def translate_mod(mod: dict, translations: dict) -> dict:
    out = dict(mod)
    unique_name = mod.get("uniqueName", "")
    for field in TRANSLATABLE_FIELDS:
        zh = get_translation(translations, unique_name, field)
        if zh:
            out[field] = zh
    return out


def build_all(official: dict, translations: dict) -> tuple[dict, list[dict]]:
    database_zh = dict(official)
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
                    "authorDisplay": out_mod.get("authorDisplay", ""),
                    "downloadUrl": out_mod.get("downloadUrl", ""),
                    "repo": out_mod.get("repo", ""),
                    "tags": out_mod.get("tags", []),
                    "slug": out_mod.get("slug", ""),
                    "thumbnail": out_mod.get("thumbnail", {}),
                    "downloadCount": out_mod.get("downloadCount", 0),
                    "installCount": out_mod.get("installCount", 0),
                    "weeklyInstallCount": out_mod.get("weeklyInstallCount", 0),
                    "version": out_mod.get("version", ""),
                    "latestReleaseDate": out_mod.get("latestReleaseDate", ""),
                    "firstReleaseDate": out_mod.get("firstReleaseDate", ""),
                    "latestReleaseDescription": out_mod.get("latestReleaseDescription", ""),
                })
        database_zh[group] = out_group
    return database_zh, mods_data


def deploy_site(site_dir: Path, dist_dir: Path) -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)
    for item in site_dir.iterdir():
        target = dist_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Chinese database.json and website data")
    parser.add_argument("--official", default="source/official.json")
    parser.add_argument("--translations", default="source/translations.json")
    parser.add_argument("--site", default=str(SITE_SOURCE))
    parser.add_argument("--dist", default=str(DIST))
    args = parser.parse_args()

    official = load_json(Path(args.official))
    translations = load_translations(Path(args.translations))
    database_zh, mods_data = build_all(official, translations)

    dist = Path(args.dist)
    (dist / "data").mkdir(parents=True, exist_ok=True)
    save_json(dist / "database.json", database_zh)
    save_json(dist / "data" / "mods.json", {"mods": mods_data})
    deploy_site(Path(args.site), dist)
    print(f"已生成 {dist/'database.json'} 与 {dist/'data'/'mods.json'},MOD 数: {len(mods_data)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest scripts/test/test_build.py -q`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add scripts/build.py scripts/test/test_build.py
git commit -m "feat: 生成中文 database.json 与网站数据"
```

---

### Task 6: 网站(官方站点的翻译镜像: 首页 + 列表页 + 详情页)

**背景:** 官方站点 `ow-mods/outerwildsmods.com` 公开可读(Svelte),但**无 License** → 只能参考其设计,不能复制代码。本站自行实现,做成"翻译过的镜像站": 布局与配色参照官方(深色底 `#0b0d10`、强调色 `#ff9c86`、次级文字 `rgba(255,255,255,.65)`、卡片网格),内容为中文。

**Files:**
- Create: `site/index.html`(首页: 标题 + 总数 + "热门 MOD/热门新 MOD/最近更新"三栏)
- Create: `site/mods.html`(全部 MOD 列表页: 搜索 + 分类筛选 + 卡片网格)
- Create: `site/mod.html`(详情页)
- Create: `site/css/style.css`
- Create: `site/js/app.js`
- Create: `scripts/test/test_site_smoke.py`

**Interfaces:**
- Consumes: `dist/data/mods.json`(Task 5 产物,格式 `{"mods": [{"uniqueName", "name", "description", "authorDisplay", "downloadUrl", "repo", "tags", "slug", "thumbnail", "downloadCount", "installCount", "weeklyInstallCount", "version", "latestReleaseDate", "firstReleaseDate", "latestReleaseDescription"}]}`)
- Produces: 网站源文件;冒烟测试验证生成产物结构

**页面约定:**
- `index.html` — 首页: hero(标题 + 总数说明)+ 三个栏目(热门 MOD / 热门新 MOD / 最近更新,各 3 张卡片)+ 页脚注明"非官方翻译镜像"
- `mods.html` — 列表页: 搜索框 + 分类下拉 + MOD 卡片网格,详情链接 `mod.html?uniqueName=…`
- `mod.html` — 详情页: 从 URL 参数取 `uniqueName`,渲染完整简介、更新说明、下载/仓库按钮
- 排序规则: 热门=installCount 降序(兜底 downloadCount);热门新=首次发布 60 天内按 installCount 降序;最近更新=latestReleaseDate 降序
- 客户端渲染: `app.js` fetch `data/mods.json`,同一文件处理三个页面(依次检测 `#featured` / `#mod-grid` / `#detail`)

- [ ] **Step 1: 写失败冒烟测试**

`scripts/test/test_site_smoke.py`:
```python
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
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "database.json").write_text(json.dumps(database, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "data" / "mods.json").write_text(json.dumps({"mods": mods_data}, ensure_ascii=False), encoding="utf-8")
    return database, mods_data


def test_site_files_exist():
    for rel in ("index.html", "mods.html", "mod.html", "css/style.css", "js/app.js"):
        assert (REPO_ROOT / "site" / rel).exists(), f"缺少 site/{rel}"


def test_dist_artifacts_and_json_valid(tmp_path):
    database, mods_data = _run_build(tmp_path)
    assert '"releases"' in (tmp_path / "database.json").read_text(encoding="utf-8")
    mods = json.loads((tmp_path / "data" / "mods.json").read_text(encoding="utf-8"))["mods"]
    assert len(mods) == len(mods_data) == 2
    required_keys = {"uniqueName", "name", "description", "authorDisplay", "downloadUrl",
                     "repo", "tags", "slug", "thumbnail", "downloadCount", "installCount",
                     "weeklyInstallCount", "version", "latestReleaseDate", "firstReleaseDate",
                     "latestReleaseDescription"}
    for mod in mods:
        assert required_keys <= set(mod.keys())


def test_mirror_pages_cover_three_views():
    index = (REPO_ROOT / "site" / "index.html").read_text(encoding="utf-8")
    mods = (REPO_ROOT / "site" / "mods.html").read_text(encoding="utf-8")
    assert "featured" in index   # 首页三栏
    assert "mod-grid" in mods    # 列表页网格
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert "uniqueName" in js    # 详情页从 URL 参数读 uniqueName
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest scripts/test/test_site_smoke.py -q`
Expected: FAIL — `assert (REPO_ROOT / "site" / "index.html").exists()`

- [ ] **Step 3: 实现网站文件**

`site/index.html`(首页,参照官方首页结构):
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>星际拓荒 MOD 数据库</title>
<link rel="stylesheet" href="css/style.css">
</head>
<body>
<header class="site-header">
  <nav>
    <a class="brand" href="index.html">星际拓荒 MOD</a>
    <a href="mods.html">全部 MOD</a>
  </nav>
</header>
<main>
  <section class="hero">
    <h1>星际拓荒 MOD</h1>
    <p class="intro">是《星际拓荒》的非官方修改,可添加新功能、改进与额外内容。使用
      <a class="link" href="https://outerwildsmods.com/mod-manager" target="_blank" rel="noopener">Mod Manager</a>
      即可轻松下载安装。<span id="mod-total"></span></p>
  </section>
  <section id="featured"></section>
</main>
<footer>
  <p>非官方翻译镜像站 · 数据来自
    <a class="link" href="https://outerwildsmods.com" target="_blank" rel="noopener">outerwildsmods.com</a>
    · AI 自动汉化 · 人工精校持续更新</p>
</footer>
<script src="js/app.js"></script>
</body>
</html>
```

`site/mods.html`(全部 MOD 列表页):
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>全部 MOD — 星际拓荒 MOD 数据库</title>
<link rel="stylesheet" href="css/style.css">
</head>
<body>
<header class="site-header">
  <nav>
    <a class="brand" href="index.html">星际拓荒 MOD</a>
    <a href="mods.html">全部 MOD</a>
  </nav>
</header>
<main>
  <h1>全部 MOD</h1>
  <div class="controls">
    <input id="search" type="search" placeholder="搜索 MOD 名称 / 简介…">
    <select id="tag-filter"><option value="">全部分类</option></select>
    <span id="count"></span>
  </div>
  <div id="mod-grid" class="grid"></div>
</main>
<script src="js/app.js"></script>
</body>
</html>
```

`site/mod.html`(详情页):
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MOD 详情 — 星际拓荒 MOD 数据库</title>
<link rel="stylesheet" href="css/style.css">
</head>
<body>
<header class="site-header">
  <nav>
    <a class="brand" href="index.html">星际拓荒 MOD</a>
    <a href="mods.html">全部 MOD</a>
  </nav>
</header>
<main id="detail"></main>
<script src="js/app.js"></script>
</body>
</html>
```

`site/css/style.css`(配色参照官方: 底 `#0b0d10`、强调 `#ff9c86`、次级文字半透明白):
```css
:root { color-scheme: dark; }
body { font-family: system-ui, "PingFang SC", "Microsoft YaHei", sans-serif;
       margin: 0; background: #0b0d10; color: #fff; }
.site-header { border-bottom: 1px solid rgba(255,255,255,.12); }
.site-header nav { max-width: 1100px; margin: 0 auto; padding: .9rem 1rem;
                   display: flex; gap: 1.5rem; align-items: center; }
.site-header a { color: #fff; text-decoration: none; opacity: .8; }
.site-header a:hover { opacity: 1; }
.site-header .brand { font-weight: 700; font-size: 1.1rem; opacity: 1; }
main { max-width: 1100px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
footer { max-width: 1100px; margin: 0 auto; padding: 0 1rem 2rem;
         color: rgba(255,255,255,.5); font-size: .85rem; }
.hero h1 { font-size: 1.6rem; margin: .5rem 0; }
.intro { color: rgba(255,255,255,.65); line-height: 1.7; }
.link { color: #ff9c86; text-decoration: none; }
.link:hover { text-decoration: underline; }
section h2 { font-size: 1.25rem; margin: 2rem 0 1rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }
.mod-card { display: block; padding: 1rem; border: 1px solid rgba(255,255,255,.12);
            border-radius: 10px; background: rgba(255,255,255,.04); text-decoration: none; color: #fff; }
.mod-card:hover { border-color: #ff9c86; }
.mod-card .thumb { width: 100%; aspect-ratio: 16/9; object-fit: cover; border-radius: 6px;
                   background: rgba(255,255,255,.06); }
.mod-card h3 { margin: .6rem 0 .2rem; font-size: 1.05rem; }
.mod-card .meta { color: rgba(255,255,255,.65); font-size: .85rem; }
.mod-card .desc { margin: .4rem 0 0; font-size: .9rem; color: rgba(255,255,255,.8);
                  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.controls { display: flex; gap: .5rem; margin: 1rem 0; flex-wrap: wrap; }
.controls input, .controls select { padding: .5rem; border-radius: 6px; border: 1px solid rgba(255,255,255,.2);
                                    background: rgba(255,255,255,.06); color: #fff; }
#search { flex: 1; min-width: 200px; }
#count { align-self: center; color: rgba(255,255,255,.65); font-size: .9rem; }
.detail h1 { margin: .25rem 0; }
.detail .meta { color: rgba(255,255,255,.65); margin-bottom: 1rem; }
.detail .buttons { display: flex; gap: .75rem; margin: 1rem 0; }
.detail .buttons a { padding: .55rem 1.2rem; border-radius: 8px; text-decoration: none;
                     background: #ff9c86; color: #0b0d10; font-weight: 600; }
.detail .buttons a.secondary { background: rgba(255,255,255,.12); color: #fff; }
.detail .section { border: 1px solid rgba(255,255,255,.12); border-radius: 10px;
                   padding: 1rem 1.25rem; margin-top: 1.25rem; background: rgba(255,255,255,.04); }
.detail .section h3 { margin: 0 0 .5rem; font-size: 1rem; }
.tag { display: inline-block; padding: .15rem .6rem; border-radius: 999px;
       background: rgba(255,255,255,.1); color: rgba(255,255,255,.8); font-size: .75rem; margin-right: .35rem; }
.placeholder { color: rgba(255,255,255,.65); text-align: center; padding: 2rem; }
```

`site/js/app.js`(三个页面共用;依次检测 `#featured` 首页 / `#mod-grid` 列表页 / `#detail` 详情页):
```js
async function loadMods() {
  const resp = await fetch("data/mods.json");
  if (!resp.ok) throw new Error("无法加载数据: " + resp.status);
  return (await resp.json()).mods;
}

function esc(s) {
  const div = document.createElement("div");
  div.textContent = String(s == null ? "" : s);
  return div.innerHTML;
}

function thumbUrl(m) {
  return m.thumbnail && m.thumbnail.main
    ? "https://ow-mods.github.io/ow-mod-db/images/" + m.thumbnail.main
    : "";
}

function cardHtml(m) {
  const thumb = thumbUrl(m);
  return `<a class="mod-card" href="mod.html?uniqueName=${encodeURIComponent(m.uniqueName)}">
    ${thumb ? `<img class="thumb" src="${esc(thumb)}" alt="" loading="lazy">` : ""}
    <h3>${esc(m.name)}</h3>
    <div class="meta">${esc(m.authorDisplay)} · v${esc(m.version)} · ${esc(m.downloadCount)} 次下载</div>
    <p class="desc">${esc(m.description)}</p>
  </a>`;
}

function installs(m) {
  return (m.installCount || 0) || (m.downloadCount || 0);
}

function sortMods(mods, mode) {
  const copy = [...mods];
  if (mode === "installs") {
    return copy.sort((a, b) => installs(b) - installs(a));
  }
  if (mode === "updated") {
    return copy.sort((a, b) => String(b.latestReleaseDate).localeCompare(String(a.latestReleaseDate)));
  }
  if (mode === "popularNew") {
    const cutoff = Date.now() - 60 * 24 * 3600 * 1000;
    const recent = copy.filter((m) => m.firstReleaseDate && new Date(m.firstReleaseDate).getTime() >= cutoff);
    return recent.sort((a, b) => installs(b) - installs(a));
  }
  return copy;
}

function renderHome(mods) {
  const total = document.getElementById("mod-total");
  if (total) total.textContent = `目前共有 ${mods.length} 个 MOD、扩展与工具。`;
  const featured = document.getElementById("featured");
  if (!featured) return;
  const sections = [
    ["热门 MOD", "installs"],
    ["热门新 MOD", "popularNew"],
    ["最近更新", "updated"],
  ];
  featured.innerHTML = sections.map(([title, mode]) => {
    const items = sortMods(mods, mode).slice(0, 3);
    return `<section><h2>${title}</h2><div class="grid">${items.map(cardHtml).join("")}</div></section>`;
  }).join("");
}

function renderList(mods) {
  const grid = document.getElementById("mod-grid");
  const search = document.getElementById("search");
  const tagFilter = document.getElementById("tag-filter");
  const count = document.getElementById("count");
  if (!grid) return;

  const allTags = [...new Set(mods.flatMap((m) => m.tags || []))].sort();
  for (const tag of allTags) {
    const opt = document.createElement("option");
    opt.value = tag;
    opt.textContent = tag;
    tagFilter.appendChild(opt);
  }

  function draw() {
    const q = search.value.trim().toLowerCase();
    const tag = tagFilter.value;
    const shown = mods.filter((m) => {
      if (tag && !(m.tags || []).includes(tag)) return false;
      if (!q) return true;
      return (m.name + " " + m.description + " " + m.authorDisplay).toLowerCase().includes(q);
    });
    count.textContent = shown.length + " / " + mods.length + " 个 MOD";
    grid.innerHTML = shown.map(cardHtml).join("") || `<p class="placeholder">没有匹配的 MOD</p>`;
  }

  search.addEventListener("input", draw);
  tagFilter.addEventListener("change", draw);
  draw();
}

function renderDetail(mods) {
  const params = new URLSearchParams(location.search);
  const uniqueName = params.get("uniqueName");
  const mod = mods.find((m) => m.uniqueName === uniqueName);
  const main = document.getElementById("detail");
  if (!main) return;
  if (!mod) {
    main.innerHTML = `<p class="placeholder">未找到该 MOD,<a class="link" href="mods.html">返回列表</a></p>`;
    document.title = "未找到 — 星际拓荒 MOD 数据库";
    return;
  }
  document.title = mod.name + " — 星际拓荒 MOD 数据库";
  const thumb = thumbUrl(mod);
  main.innerHTML = `
    <div class="detail">
      ${thumb ? `<img class="thumb" src="${esc(thumb)}" alt="">` : ""}
      <h1>${esc(mod.name)}</h1>
      <div class="meta">${esc(mod.authorDisplay)} · v${esc(mod.version)} · ${esc(mod.downloadCount)} 次下载 · 更新于 ${esc((mod.latestReleaseDate || "").slice(0, 10))}</div>
      <div>${(mod.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      <div class="buttons">
        <a href="${esc(mod.downloadUrl)}" target="_blank" rel="noopener">下载 MOD</a>
        ${mod.repo ? `<a class="secondary" href="${esc(mod.repo)}" target="_blank" rel="noopener">源代码仓库</a>` : ""}
      </div>
      ${mod.description ? `<div class="section"><h3>简介</h3><p>${esc(mod.description)}</p></div>` : ""}
      ${mod.latestReleaseDescription ? `<div class="section"><h3>最新版本更新说明</h3><p>${esc(mod.latestReleaseDescription)}</p></div>` : ""}
    </div>`;
}

loadMods()
  .then((mods) => {
    if (document.getElementById("featured")) renderHome(mods);
    else if (document.getElementById("mod-grid")) renderList(mods);
    else renderDetail(mods);
  })
  .catch((err) => {
    const target = document.getElementById("detail")
      || document.getElementById("mod-grid")
      || document.getElementById("featured");
    if (target) target.innerHTML = `<p class="placeholder">加载失败:${esc(err.message)}</p>`;
  });
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest scripts/test/test_site_smoke.py -q`
Expected: 4 passed

- [ ] **Step 5: 本地人工验证页面**

Run:
```bash
python scripts/build.py
python -m http.server 8000 --directory dist
```
浏览器检查:
- `http://localhost:8000/` — 首页 hero(含 MOD 总数)+ 三个栏目(热门/热门新/最近更新),各 3 张卡片
- `http://localhost:8000/mods.html` — 列表渲染、搜索、分类筛选
- 点任意卡片 → `mod.html?uniqueName=…` 详情页(简介、更新说明、下载按钮)
确认无 console 错误。

- [ ] **Step 6: 提交**

```bash
git add site/ scripts/test/test_site_smoke.py
git commit -m "feat: 中文 MOD 网站(官方翻译镜像: 首页/列表/详情页)"
```

---

### Task 7: GitHub Actions 流水线与 README

**Files:**
- Create: `.github/workflows/sync-translate.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: Task 1-6 全部脚本与产物约定
- Produces: 可部署的 CI 流水线 + 使用文档

- [ ] **Step 1: 写 workflow 文件**

`.github/workflows/sync-translate.yml`:
```yaml
name: sync-translate
on:
  schedule:
    - cron: '0 */6 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  sync-translate-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: python -m pytest scripts/test -q

      - name: Sync official database
        run: python scripts/sync.py

      - name: Translate with AI
        env:
          OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
        run: python scripts/translate.py

      - name: Build artifacts
        run: python scripts/build.py

      - name: Commit translation cache back to main
        run: |
          git config user.name "ow-mod-db bot"
          git config user.email "ow-mod-db-bot@users.noreply.github.com"
          git add source/translations.json source/pending.json source/official.json
          git diff --cached --quiet || git commit -m "chore: 更新翻译缓存 [skip ci]"
          git push

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./dist
          force_orphan: true
```

- [ ] **Step 2: 写 README.md**

`README.md`:
```markdown
# 星际拓荒 MOD 数据库(汉化版)

自动同步 [官方 MOD 数据库](https://ow-mods.github.io/ow-mod-db/database.json),用 AI 将 MOD 名称、简介、更新说明汉化为简体中文,部署为:

- **中文网站**: 官方站点的翻译镜像(首页三栏/全部 MOD 列表/详情页,参照官方布局与配色)
- **可替换 database.json**: 在 Outer Wilds Mod Manager 中把数据库网址改为本仓库的 GitHub Pages 地址,游戏内即可看到中文简介

## 部署前准备(一次性)

1. 推送本仓库到 GitHub
2. 仓库 Settings → Pages → Source 选择 `gh-pages` 分支(首次部署后生效)
3. 仓库 Settings → Secrets and variables → Actions,添加:
   - `OPENAI_BASE_URL` — OpenAI 兼容接口地址(如 `https://api.deepseek.com/v1`)
   - `OPENAI_API_KEY` — API Key
   - `OPENAI_MODEL` — 模型名(如 `deepseek-chat`)
4. 手动触发一次 Actions 的 `sync-translate` 工作流验证

之后每天 0/6/12/18 点自动同步翻译。首次运行会全量翻译,之后只翻译新增/变更的字段。

## 让玩家使用中文数据库

Mod Manager 设置 → Advanced → Database URL 改为:
`https://<你的用户名>.github.io/ow-mod-db/database.json`

## 维护

### 专有名词表 `source/glossary.json`
AI 翻译必须遵守的术语表。团队发现新专有名词直接加条目,提交后下次同步自动生效:

```json
{ "Nomai": "挪麦" }
```

### 人工翻译覆盖 `source/human_translations.json`
人工精校优先于 AI,格式:

```json
{
  "Alek.OWML": {
    "description": "人工精校版简介"
  }
}
```

## 本地运行(调试)

```bash
pip install -r requirements.txt
python scripts/sync.py                      # 下载官方库 + 生成待翻译清单
python scripts/translate.py --dry-run       # 只统计,不调 API
python scripts/translate.py                 # 真实翻译(需环境变量)
python scripts/build.py                     # 生成 dist/
python -m http.server 8000 --directory dist # 预览网站
python -m pytest scripts/test -q            # 测试
```

## 测试

`python -m pytest scripts/test -q`
```

- [ ] **Step 3: 校验 workflow YAML 语法**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/sync-translate.yml')); print('YAML OK')"`
Expected: `YAML OK`(若未装 pyyaml,先 `pip install pyyaml` 或跳过此步由 GitHub 侧校验)

- [ ] **Step 4: 提交**

```bash
git add .github/workflows/sync-translate.yml README.md
git commit -m "feat: CI 流水线与使用文档"
```

---

### Task 8: 端到端验证(真实官方库 + dry-run)

**Files:**
- 无新增文件(验证任务)

**目的:** 用真实官方库跑通全流程,验证产物结构与官方一致、翻译缓存正确落盘。

- [ ] **Step 1: 跑全流程 dry-run**

```bash
pip install -r requirements.txt
python scripts/sync.py
python scripts/translate.py --dry-run
python scripts/build.py
```

Expected:
- sync 输出待翻译数量(首次约 800+ 条: name/description/latestReleaseDescription 非空字段)
- translate dry-run 打印条数,不调 API
- build 成功生成 `dist/database.json`、`dist/data/mods.json`

- [ ] **Step 2: 校验 database.json 结构与官方一致**

```bash
python - <<'EOF'
import json
from pathlib import Path

official = json.loads(Path("source/official.json").read_text(encoding="utf-8"))
built = json.loads(Path("dist/database.json").read_text(encoding="utf-8"))
assert set(built.keys()) == set(official.keys())
for group in ("releases", "alphaReleases"):
    assert len(built[group]) == len(official[group])
    for out, src in zip(built[group], official[group]):
        assert set(out.keys()) == set(src.keys())
        for k, v in src.items():
            if k not in ("name", "description", "latestReleaseDescription"):
                assert out[k] == v, f"字段 {k} 不应改动"
print("结构一致性校验通过:", len(built["releases"]), "releases,",
      len(built["alphaReleases"]), "alphaReleases")
EOF
```

Expected: `结构一致性校验通过: 413 releases, N alphaReleases`

- [ ] **Step 3: 校验网站数据 JSON 合法且非空**

```bash
python -c "import json; d=json.load(open('dist/data/mods.json')); print('网站数据 MOD 数:', len(d['mods']))"
```

Expected: `网站数据 MOD 数: 413`

- [ ] **Step 4: 提交验证产物(translations.json 为空时不提交)**

若 `source/translations.json`、`source/pending.json` 有变化:
```bash
git add source/ && git commit -m "chore: 首次同步生成待翻译清单" || true
```

- [ ] **Step 5: 收尾说明**

向用户交付:
1. 推送到 GitHub 后添加 3 个 Secrets
2. 手动触发 workflow 完成首次全量翻译(需真实 API Key)
3. 验证网站与 database.json
