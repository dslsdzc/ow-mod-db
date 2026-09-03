import httpx
import pytest

import ai_client
from ai_client import AIError

# 参数化前 SYSTEM_PROMPT 的历史全文(target_lang="简体中文" 时输出必须与之逐字节一致)
_LEGACY_SYSTEM_PROMPT = (
    "You are a professional game mod localization translator. "
    "Translate English Outer Wilds mod metadata to Simplified Chinese.\n"
    "Rules:\n"
    "1. Glossary terms must be translated to exactly the given Chinese "
    "(e.g. Quantum Moon -> 量子卫星).\n"
    "2. Character names on their FIRST mention in the text must appear as "
    "\"EnglishName(中文名)\" (e.g. \"Hornfels(霍恩费斯)\"); later mentions "
    "in the same text use only the Chinese name.\n"
    "3. Proper nouns not in either list stay in English.\n"
    "4. Keep Markdown formatting, line breaks, URLs, and angle brackets intact.\n"
    "5. Output only the translation, no quotes, no explanation.\n"
    "Glossary:\n{glossary}"
)


def _rules(prompt: str) -> list[str]:
    """提取 "Rules:" 下、"Glossary:" 前的编号规则行(1.~5.),用于比对规则条数/结构。"""
    rules = prompt.split("Rules:\n", 1)[1].split("\nGlossary:", 1)[0]
    return [line for line in rules.split("\n") if line[:2] in {"1.", "2.", "3.", "4.", "5."}]


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
        {"terms": {"Nomai": "挪麦"}, "characters": {"Hornfels": "霍恩费斯"}},
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
    assert "Hornfels -> 霍恩费斯" in system
    assert "[专有名词,直接译为中文]" in system
    assert "[角色名,首次出现用 原名(中文) 格式]" in system
    assert "The mod loader for Outer Wilds" in payload["messages"][1]["content"]


def test_batch_translate_success(monkeypatch):
    fake = FakePost(httpx.Response(
        200, json={"choices": [{"message": {"content": '{"0": "甲", "1": "乙"}'}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    result = ai_client.translate_batch_with_ai(
        ["a", "b"], {"terms": {}}, base_url="u", api_key="k", model="m")
    assert result == {0: "甲", 1: "乙"}
    user = fake.calls[0][1]["messages"][1]["content"]
    assert "0: a" in user and "1: b" in user and "JSON object" in user


def test_batch_translate_handles_code_fence_and_missing(monkeypatch):
    fake = FakePost(httpx.Response(
        200, json={"choices": [{"message": {"content": '```json\n{"0": "甲"}\n```'}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    result = ai_client.translate_batch_with_ai(
        ["a", "b"], {}, base_url="u", api_key="k", model="m")
    assert result == {0: "甲"}  # 缺失的序号不返回


def test_batch_translate_repairs_bad_escapes(monkeypatch):
    # 模型把 C:\Users 原样输出(非法 \U 转义)→ 解析器应修复
    raw = '{"0": "修复 C:\\Users\\game 的 bug"}'   # 实际含单反斜杠
    fake = FakePost(httpx.Response(200, json={"choices": [{"message": {"content": raw}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    result = ai_client.translate_batch_with_ai(["fix bug"], {}, base_url="u", api_key="k", model="m")
    assert result == {0: "修复 C:\\Users\\game 的 bug"}


def test_batch_translate_invalid_json_raises(monkeypatch):
    fake = FakePost(httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    with pytest.raises(AIError, match="not valid JSON"):
        ai_client.translate_batch_with_ai(["a"], {}, base_url="u", api_key="k", model="m")


def test_base_url_already_ends_with_completions(monkeypatch):
    fake = FakePost(httpx.Response(200, json={"choices": [{"message": {"content": "译"}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    ai_client.translate_with_ai(
        "Hi", {}, base_url="https://api.example.com/v4/chat/completions", api_key="k", model="m")
    assert fake.calls[0][0] == "https://api.example.com/v4/chat/completions"  # 不重复拼接


def test_batch_translate_empty_texts_no_request(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("不应发起请求")

    monkeypatch.setattr(ai_client.httpx, "post", boom)
    assert ai_client.translate_batch_with_ai([], {}, base_url="u", api_key="k", model="m") == {}


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


def test_translate_null_content_raises(monkeypatch):
    fake = FakePost(httpx.Response(200, json={"choices": [{"message": {"content": None}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    with pytest.raises(AIError, match="not a string"):
        ai_client.translate_with_ai("Hi", {}, base_url="u", api_key="k", model="m")


def test_translate_non_dict_json_raises(monkeypatch):
    fake = FakePost(httpx.Response(200, json=["not", "a", "dict"]))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    with pytest.raises(AIError, match="unexpected API response"):
        ai_client.translate_with_ai("Hi", {}, base_url="u", api_key="k", model="m")


def test_target_lang_in_user_prompt(monkeypatch):
    fake = FakePost(httpx.Response(200, json={"choices": [{"message": {"content": "こんにちは"}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    ai_client.translate_with_ai("Hello", {}, base_url="u", api_key="k", model="m", target_lang="日本語")
    user = fake.calls[0][1]["messages"][1]["content"]
    assert "日本語" in user


def test_target_lang_in_batch_user_prompt(monkeypatch):
    fake = FakePost(httpx.Response(
        200, json={"choices": [{"message": {"content": '{"0": "こんにちは"}'}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    ai_client.translate_batch_with_ai(
        ["Hello"], {}, base_url="u", api_key="k", model="m", target_lang="日本語")
    user = fake.calls[0][1]["messages"][1]["content"]
    assert "日本語" in user


def test_default_system_prompt_matches_legacy_text():
    """默认(简体中文)系统提示必须与参数化前逐字节一致:默认值与显式 简体中文 都走历史文本。"""
    assert ai_client.system_prompt() == _LEGACY_SYSTEM_PROMPT
    assert ai_client.system_prompt("简体中文") == _LEGACY_SYSTEM_PROMPT


def test_japanese_system_prompt_is_language_neutral():
    """日本語 路径:语言名注入头部,且不残留 "Simplified Chinese"/"中文" 等中文专属措辞;
    规则条数/结构(规则 1.~5. + Glossary 行)与 zh 历史版一致。"""
    prompt = ai_client.system_prompt("日本語")
    assert "日本語" in prompt
    assert "Simplified Chinese" not in prompt
    assert "中文" not in prompt
    assert prompt.endswith("Glossary:\n{glossary}")
    assert len(_rules(prompt)) == len(_rules(_LEGACY_SYSTEM_PROMPT)) == 5


def test_glossary_block_zh_labels_unchanged_and_ja_labels_neutral():
    """术语表区块:zh 标签逐字不变;日本語 用中性标签且不含中文指令措辞。"""
    glossary = {"terms": {"Quantum Moon": "量子の月"}, "characters": {"Hornfels": "ホーンフェルス"}}
    zh_block = ai_client._glossary_block(glossary, "简体中文")
    assert zh_block == (
        "[专有名词,直接译为中文]\n"
        "Quantum Moon -> 量子の月\n"
        "[角色名,首次出现用 原名(中文) 格式]\n"
        "Hornfels -> ホーンフェルス"
    )
    ja_block = ai_client._glossary_block(glossary, "日本語")
    assert "Quantum Moon -> 量子の月" in ja_block and "Hornfels -> ホーンフェルス" in ja_block
    assert "[专有名词,直接译为中文]" not in ja_block
    assert "[角色名,首次出现用 原名(中文) 格式]" not in ja_block
    assert "Simplified Chinese" not in ja_block and "中文" not in ja_block


def test_default_translate_sends_byte_identical_system_message(monkeypatch):
    """默认 target_lang 的单条翻译:发出去的 system 消息与参数化前逐字节一致。"""
    fake = FakePost(httpx.Response(200, json={"choices": [{"message": {"content": "译"}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    glossary = {"terms": {"Nomai": "挪麦"}, "characters": {"Hornfels": "霍恩费斯"}}
    ai_client.translate_with_ai("Hi", glossary, base_url="u", api_key="k", model="m")
    system = fake.calls[0][1]["messages"][0]["content"]
    expected_block = (
        "[专有名词,直接译为中文]\n"
        "Nomai -> 挪麦\n"
        "[角色名,首次出现用 原名(中文) 格式]\n"
        "Hornfels -> 霍恩费斯"
    )
    assert system == _LEGACY_SYSTEM_PROMPT.format(glossary=expected_block)


def test_japanese_translate_system_message_is_language_neutral(monkeypatch):
    """日本語 单条翻译:system 与 user 消息都含 日本語;system 不含中文专属措辞。"""
    fake = FakePost(httpx.Response(200, json={"choices": [{"message": {"content": "こんにちは"}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    glossary = {"terms": {"Quantum Moon": "量子の月"}, "characters": {"Hornfels": "ホーンフェルス"}}
    ai_client.translate_with_ai(
        "Hello", glossary, base_url="u", api_key="k", model="m", target_lang="日本語")
    messages = fake.calls[0][1]["messages"]
    system, user = messages[0]["content"], messages[1]["content"]
    assert "日本語" in system
    assert "Simplified Chinese" not in system and "中文" not in system
    assert "日本語" in user


def test_japanese_batch_system_message_is_language_neutral(monkeypatch):
    """日本語 批量翻译:system 与 user 消息都含 日本語;system 不含中文专属措辞。"""
    fake = FakePost(httpx.Response(
        200, json={"choices": [{"message": {"content": '{"0": "こんにちは"}'}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    glossary = {"terms": {"Quantum Moon": "量子の月"}, "characters": {"Hornfels": "ホーンフェルス"}}
    ai_client.translate_batch_with_ai(
        ["Hello"], glossary, base_url="u", api_key="k", model="m", target_lang="日本語")
    messages = fake.calls[0][1]["messages"]
    system, user = messages[0]["content"], messages[1]["content"]
    assert "日本語" in system
    assert "Simplified Chinese" not in system and "中文" not in system
    assert "日本語" in user
