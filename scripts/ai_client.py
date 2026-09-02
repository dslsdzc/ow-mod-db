"""OpenAI-compatible chat-completions client for translation."""

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
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise AIError(f"unexpected API response: {e}") from e
    if not isinstance(content, str):
        raise AIError("unexpected API response: content is not a string")
    return content.strip()
