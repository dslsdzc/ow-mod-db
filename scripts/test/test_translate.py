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


def test_consecutive_failures_abort():
    translations = {}
    fake = FakeAI(failures=99)  # 永远失败
    no_sleep = lambda _s: None
    pending = _pending() * 5  # 15 条,全走 AI 且全失败
    with pytest.raises(translate.ConsecutiveFailureError):
        translate.translate_pending(pending, translations, {}, {}, fake, at="t", sleep=no_sleep,
                                    max_consecutive_failures=5)
    assert translations == {}  # 前 5 条都失败,无成功写入


def test_consecutive_failures_reset_by_human_override():
    translations = {}
    fake = FakeAI(failures=99)
    no_sleep = lambda _s: None
    # 4 条 AI 失败后插 1 条人工覆盖(重置计数),再 5 条失败应触发中止
    human = {"Test.Mod": {"description": "人工"}}
    pending = [{"unique_name": "A", "field": "description", "en": "a"}] * 4 + \
              [{"unique_name": "Test.Mod", "field": "description", "en": "English text"}] + \
              [{"unique_name": "B", "field": "description", "en": "b"}] * 5
    with pytest.raises(translate.ConsecutiveFailureError):
        translate.translate_pending(pending, translations, human, {}, fake, at="t", sleep=no_sleep,
                                    max_consecutive_failures=5)
    assert translations["Test.Mod"]["description"]["zh"] == "人工"


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
