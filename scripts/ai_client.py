"""OpenAI-compatible chat-completions client for translation."""

import json
import re

import httpx

SYSTEM_PROMPT = (
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


class AIError(Exception):
    pass


def _glossary_block(glossary: dict) -> str:
    """Build the prompt glossary section from {"terms": {...}, "characters": {...}}."""
    if not glossary:
        return "(empty)"
    terms = glossary.get("terms") or {}
    characters = glossary.get("characters") or {}
    if not terms and not characters:
        return "(empty)"
    parts = []
    if terms:
        parts.append("[专有名词,直接译为中文]")
        parts.extend(f"{en} -> {zh}" for en, zh in terms.items())
    if characters:
        parts.append("[角色名,首次出现用 原名(中文) 格式]")
        parts.extend(f"{en} -> {zh}" for en, zh in characters.items())
    return "\n".join(parts)


def _chat_completion(user_content: str, glossary: dict, *, base_url: str, api_key: str,
                     model: str) -> str:
    """POST one chat completion; returns stripped content. Raises AIError on any failure."""
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(glossary=_glossary_block(glossary))},
            {"role": "user", "content": user_content},
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
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise AIError(f"unexpected API response: {e}") from e
    if not isinstance(content, str):
        raise AIError("unexpected API response: content is not a string")
    return content.strip()


def translate_with_ai(en_text: str, glossary: dict, *, base_url: str, api_key: str, model: str) -> str:
    """Translate a single English text via an OpenAI-compatible chat API.

    Returns the translated text (stripped). Raises AIError on any failure.
    """
    return _chat_completion(
        "Translate the following text to Simplified Chinese.\nText:\n" + en_text,
        glossary, base_url=base_url, api_key=api_key, model=model,
    )


def _parse_json_content(content: str) -> dict:
    """把模型输出解析成 {int 序号: 译文};失败抛 AIError."""
    cleaned = re.sub(r"^```(?:json)?\n?", "", content.strip())
    cleaned = re.sub(r"\n?```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except ValueError as e:
        raise AIError(f"batch response not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise AIError("batch response not a JSON object")
    result = {}
    for key, value in data.items():
        try:
            result[int(key)] = value
        except (ValueError, TypeError):
            continue
    return result


def translate_batch_with_ai(texts: list[str], glossary: dict, *, base_url: str, api_key: str,
                            model: str) -> dict:
    """把多条文本合并为一次 chat 请求翻译;返回 {序号: 译文}(可能缺部分序号).

    Raises AIError on request-level failure or unparseable response.
    """
    if not texts:
        return {}
    lines = "\n".join(f"{i}: {t}" for i, t in enumerate(texts))
    user_content = (
        "Translate each numbered text below to Simplified Chinese.\n"
        "Reply with ONLY a JSON object mapping each number to its translation, "
        'e.g. {"0": "...", "1": "..."}. No other text, no code fences.\n\n'
        + lines
    )
    content = _chat_completion(user_content, glossary,
                               base_url=base_url, api_key=api_key, model=model)
    parsed = _parse_json_content(content)
    return {i: zh for i, zh in parsed.items() if isinstance(zh, str) and zh.strip()}
