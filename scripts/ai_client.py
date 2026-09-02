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
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise AIError(f"unexpected API response: {e}") from e
    if not isinstance(content, str):
        raise AIError("unexpected API response: content is not a string")
    return content.strip()
