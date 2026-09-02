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
