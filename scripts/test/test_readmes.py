import pytest

import readmes
from readmes import PERMISSIVE_LICENSES, chunk_markdown, is_translatable, sha256_text


class FakeAI:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def __call__(self, text):
        self.calls.append(text)
        if self.fail:
            from ai_client import AIError
            raise AIError("boom")
        return "译:" + text[:10]


def test_whitelist_contains_common_permissive():
    assert {"MIT", "Apache-2.0", "BSD-3-Clause", "Unlicense"} <= PERMISSIVE_LICENSES


def test_is_translatable_decisions():
    assert is_translatable("A", "MIT", []) == (True, "ok")
    assert is_translatable("A", "none", [])[0] is False
    assert is_translatable("A", "", [])[0] is False
    assert is_translatable("A", "GPL-3.0", [])[0] is False   # 传染性许可不在白名单
    assert is_translatable("A", "MIT", ["A"])[0] is False    # denylist 优先


def test_chunk_markdown_paragraph_boundaries():
    text = "\n\n".join(f"段落{i}" + "字" * 300 for i in range(10))
    chunks = chunk_markdown(text, max_chars=1000)
    assert all(len(c) <= 1000 for c in chunks)
    assert "".join(chunks).replace("\n\n", "") == text.replace("\n\n", "")  # 内容不丢
    assert len(chunks) >= 4


def test_chunk_oversized_single_paragraph_hard_split():
    text = "长" * 3000
    chunks = chunk_markdown(text, max_chars=1000)
    assert all(len(c) <= 1000 for c in chunks)
    assert sum(len(c) for c in chunks) == 3000


def test_sha256_stable():
    assert sha256_text("abc") == sha256_text("abc")
    assert sha256_text("abc") != sha256_text("abd")


def _official_mods():
    return {"releases": [
        {"uniqueName": "Lic.Mit", "readme": {"downloadUrl": "https://example.com/a.md"}},
        {"uniqueName": "Lic.None", "readme": {"downloadUrl": "https://example.com/b.md"}},
        {"uniqueName": "Lic.NoReadme", "readme": {}},
    ]}


def test_translate_readmes_only_licensed_and_new(monkeypatch):
    official = _official_mods()
    licenses = {"Lic.Mit": "MIT", "Lic.None": "none", "Lic.NoReadme": "MIT"}
    cache = {}
    fake = FakeAI()

    monkeypatch.setattr(readmes, "fetch_readme", lambda url: "# Title\n\nBody text here.")
    new, skipped, errors = readmes.translate_readmes(
        official, licenses, cache, [], fake, at="t", max_workers=1)

    assert new == 1
    assert skipped == 0
    assert errors == []
    assert "Lic.Mit" in cache
    assert "Lic.None" not in cache and "Lic.NoReadme" not in cache
    assert cache["Lic.Mit"]["sha"] == sha256_text("# Title\n\nBody text here.")


def test_translate_readmes_skips_unchanged_and_honors_denylist(monkeypatch):
    official = _official_mods()
    licenses = {"Lic.Mit": "MIT", "Lic.None": "none", "Lic.NoReadme": "MIT"}
    cache = {"Lic.Mit": {"sha": "same", "zh": "旧译", "at": "t0"}}
    fake = FakeAI()

    monkeypatch.setattr(readmes, "fetch_readme", lambda url: "same")
    new, skipped, errors = readmes.translate_readmes(
        official, licenses, cache, ["Lic.Mit"], fake, at="t", max_workers=1)

    assert new == 0
    assert skipped == 0          # denylist 后连"候选"都不算,不进 skip 计数
    assert cache["Lic.Mit"]["zh"] == "旧译"  # 未动
    assert fake.calls == []
