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


def test_apply_human_overrides_replaces_cached_ai():
    translations = {"Mod.A": {"name": {"en": "X", "zh": "AI旧译", "at": "t1"}}}
    human = {"Mod.A": {"name": "人工正确名"}}
    n = translate.apply_human_overrides(translations, human, "now")
    assert n == 1
    assert translations["Mod.A"]["name"]["zh"] == "人工正确名"
    assert translations["Mod.A"]["name"]["at"] == "now"
    assert translations["Mod.A"]["name"]["en"] == "X"  # en 保留


def test_apply_human_overrides_skips_absent_and_identical():
    translations = {"Mod.A": {"name": {"en": "X", "zh": "相同", "at": "t"}}}
    human = {"Mod.A": {"name": "相同", "description": "缓存里没有的字段"}}
    n = translate.apply_human_overrides(translations, human, "now")
    assert n == 0
    assert translations["Mod.A"]["name"]["zh"] == "相同"  # 未变


def test_glossary_changes_detects_value_changes_only():
    old = {"terms": {"Nomai": "挪麦", "Quantum Moon": "量子之月"},
           "characters": {"Hornfels": "霍恩费斯"}}
    new = {"terms": {"Nomai": "挪麦", "Quantum Moon": "量子卫星"},
           "characters": {"Hornfels": "霍恩费斯", "Feldspar": "费尔德斯巴"}}
    changes = translate.glossary_changes(old, new)
    # 值变了才算;未变(Nomai)与新增(Feldspar)不算
    assert changes == {"Quantum Moon": ("量子之月", "量子卫星")}


def test_apply_replacements_skips_human_fields():
    human = {"Test.Mod": {"description": "人工译文(含量子之月)"}}
    translations = {
        "Test.Mod": {"description": {"en": "x", "zh": "人工译文(含量子之月)", "at": "t"}},
        "Other.Mod": {"name": {"en": "y", "zh": "量子之月真好", "at": "t"}},
    }
    changes = {"Quantum Moon": ("量子之月", "量子卫星")}
    n = translate.apply_replacements(translations, changes, human)
    assert n == 1
    assert translations["Test.Mod"]["description"]["zh"] == "人工译文(含量子之月)"  # 人工未动
    assert translations["Other.Mod"]["name"]["zh"] == "量子卫星真好"


def test_find_affected_fields_matches_en_terms():
    translations = {
        "Mod.A": {"description": {"en": "Talk to Hornfels about the photo", "zh": "…", "at": "t"}},
        "Mod.B": {"name": {"en": "Quantum Moon mod", "zh": "…", "at": "t"}},
        "Mod.C": {"description": {"en": "Adds a ship", "zh": "…", "at": "t"}},
    }
    glossary = {"terms": {"Quantum Moon": "量子卫星"},
                "characters": {"Hornfels": "霍恩费斯"}}
    affected = translate.find_affected_fields(translations, glossary, {})
    keys = {(a["unique_name"], a["field"]) for a in affected}
    assert keys == {("Mod.A", "description"), ("Mod.B", "name")}
    assert all(a["en"] for a in affected)


def test_find_affected_fields_word_boundary():
    translations = {"Mod.X": {"description": {"en": "Hornfelsian ship part", "zh": "…", "at": "t"}}}
    glossary = {"characters": {"Hornfels": "霍恩费斯"}}
    assert translate.find_affected_fields(translations, glossary, {}) == []


def test_samples_returns_recent_successes_only():
    pending = [
        {"unique_name": "M0", "field": "description", "en": "a"},
        {"unique_name": "M1", "field": "description", "en": "b"},
        {"unique_name": "M2", "field": "description", "en": "c"},
        {"unique_name": "M3", "field": "description", "en": "d"},
    ]
    translations = {
        "M0": {"description": {"en": "a", "zh": "甲", "at": "old"}},   # 旧时间戳,不算
        "M1": {"description": {"en": "b", "zh": "乙", "at": "now"}},
        "M3": {"description": {"en": "d", "zh": "丁", "at": "now"}},   # M2 无缓存(失败)
    }
    samples = translate._samples(pending, translations, "now", n=2)
    assert samples == [("b", "乙"), ("d", "丁")]


def test_merge_pending_dedupes():
    pending = [{"unique_name": "A", "field": "name", "en": "x"}]
    translate.merge_pending(pending, [
        {"unique_name": "A", "field": "name", "en": "x"},
        {"unique_name": "B", "field": "name", "en": "y"},
    ])
    assert len(pending) == 2


def test_concurrent_translate_all_succeed():
    translations = {}
    no_sleep = lambda _s: None
    fake = FakeAI()
    human = {"M0": {"description": "人工"}}
    pending = [{"unique_name": f"M{i}", "field": "description", "en": f"text {i}"}
               for i in range(20)]
    translated, failures = translate.translate_pending(
        pending, translations, human, {}, fake, at="t", sleep=no_sleep, max_workers=8)
    assert translated == 20
    assert failures == []
    assert len(translations) == 20
    assert translations["M0"]["description"]["zh"] == "人工"   # 人工覆盖
    assert len(fake.calls) == 19                                # 人工条目不调 AI


def test_concurrent_translate_aborts_on_failure_threshold():
    translations = {}
    fake = FakeAI(failures=99999)  # 永远失败
    no_sleep = lambda _s: None
    pending = [{"unique_name": f"M{i}", "field": "description", "en": "x"}
               for i in range(200)]
    with pytest.raises(translate.ConsecutiveFailureError):
        translate.translate_pending(pending, translations, {}, {}, fake, at="t",
                                    sleep=no_sleep, max_workers=8, abort_failure_threshold=10)
    assert translations == {}


class FakeBatchAI:
    """批量 AI 替身: (texts, glossary) -> {i: zh};fail_calls 指定前 N 次调用抛错."""

    def __init__(self, fail_calls=0):
        self.fail_calls = fail_calls
        self.calls = []

    def __call__(self, texts, glossary):
        self.calls.append(texts)
        if self.fail_calls > 0:
            self.fail_calls -= 1
            raise AIError("transient batch")
        return {i: "译" + str(i) for i in range(len(texts))}


def _batched_pending(n):
    return [{"unique_name": f"M{i}", "field": "description", "en": f"text {i}"}
            for i in range(n)]


def test_make_chunks_caps_by_chars():
    long_items = [{"unique_name": f"M{i}", "field": "description", "en": "x" * 250}
                  for i in range(20)]
    chunks = translate._make_chunks(long_items, batch_size=100, batch_chars=1000)
    # 250 字/条 × 4 = 1000 → 每块最多 4 条 → 20/4 = 5 块
    assert len(chunks) == 5
    assert all(len(c) == 4 for c in chunks)


def test_batched_translate_all_succeed():
    translations = {}
    fake = FakeBatchAI()
    no_sleep = lambda _s: None
    translated, failures = translate.translate_pending_batched(
        _batched_pending(65), translations, {}, {}, fake, at="t", batch_size=30,
        sleep=no_sleep, max_workers=4)
    assert translated == 65
    assert failures == []
    assert len(fake.calls) == 3  # 65 条 → 3 个批次请求
    assert len(translations) == 65


def test_batched_translate_missing_items_fail():
    class Partial(FakeBatchAI):
        def __call__(self, texts, glossary):
            self.calls.append(texts)
            return {i: "译" for i in range(len(texts)) if i != 0}

    translations = {}
    fake = Partial()
    translated, failures = translate.translate_pending_batched(
        _batched_pending(2), translations, {}, {}, fake, at="t", batch_size=30,
        sleep=lambda _s: None)
    assert translated == 1
    assert len(failures) == 1
    assert "缺该条" in failures[0]


def test_batched_retries_then_succeeds():
    translations = {}
    fake = FakeBatchAI(fail_calls=1)  # 第一次调用失败 → 重试成功
    translated, failures = translate.translate_pending_batched(
        _batched_pending(5), translations, {}, {}, fake, at="t", batch_size=30,
        sleep=lambda _s: None)
    assert translated == 5
    assert failures == []
    assert len(fake.calls) == 2


def test_batched_human_override_skips_ai():
    translations = {}
    fake = FakeBatchAI()
    human = {"M0": {"description": "人工译"}}
    pending = [{"unique_name": "M0", "field": "description", "en": "manual text"},
               {"unique_name": "M1", "field": "description", "en": "ai text"}]
    translated, failures = translate.translate_pending_batched(
        pending, translations, human, {}, fake, at="t", batch_size=30,
        sleep=lambda _s: None)
    assert translated == 2
    assert translations["M0"]["description"]["zh"] == "人工译"
    assert fake.calls == [["ai text"]]


def test_batched_split_retry_isolates_bad_batch():
    class SplitOnly(FakeBatchAI):
        """整批调用必然失败;拆分到单条后成功."""

        def __call__(self, texts, glossary):
            self.calls.append(texts)
            if len(texts) > 1:
                raise AIError("batch too big for this model")
            return {0: "译" + texts[0][:4]}

    translations = {}
    fake = SplitOnly()
    translated, failures = translate.translate_pending_batched(
        _batched_pending(3), translations, {}, {}, fake, at="t", batch_size=10,
        batch_chars=100000, sleep=lambda _s: None)
    assert translated == 3   # 3 条都被折半重试后译出
    assert failures == []
    assert len(translations) == 3


def test_batched_aborts_after_consecutive_chunk_failures():
    translations = {}
    fake = FakeBatchAI(fail_calls=99999)
    with pytest.raises(translate.ConsecutiveFailureError):
        translate.translate_pending_batched(
            _batched_pending(100), translations, {}, {}, fake, at="t", batch_size=10,
            sleep=lambda _s: None, max_workers=2, consecutive_chunk_abort=3)
    assert translations == {}


def test_main_dry_run_calls_no_ai(tmp_path, monkeypatch):
    out = tmp_path / "translations.json"
    out.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "translate.py", "--pending", "NONEXISTENT", "--dry-run",
        "--translations", str(out), "--human", str(tmp_path / "h.json"),
        "--glossary", str(tmp_path / "g.json"),
        "--last-glossary", str(tmp_path / "last_glossary.json"),
    ])

    def boom(*a, **kw):
        raise AssertionError("dry-run 不应调用 AI")

    monkeypatch.setattr(translate.ai_client, "translate_with_ai", boom)
    translate.main()  # 不应抛错
    assert json.loads(out.read_text(encoding="utf-8")) == {}  # 缓存未变
