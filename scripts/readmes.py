"""README 预翻译流水线(仅开放许可白名单仓库).

抓取 readme.downloadUrl 的 markdown → sha256 内容哈希 → 变化才重翻 →
长文按段落拆块 → AI 逐块翻译 → 写语言目录下 readmes.json 缓存(默认 zh_cn).

尊重版权: 许可不在白名单、作者列入 denylist 的 README 一律不翻.
"""

import argparse
import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

import ai_client
from translation_store import lang_file, load_json, save_json

LANG_NAME = {"zh_cn": "简体中文", "ja": "日本語"}

# 允许预翻译的开放许可(演绎作品合法,署原作者即可)
PERMISSIVE_LICENSES = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "Unlicense", "0BSD", "MIT-0", "MPL-2.0",
}

MAX_README_CHARS = 80_000   # 超过不翻(巨大 README,日志记录)
CHUNK_CHARS = 1_400         # 单块最大字符数(段落边界切)
HEADERS = {"User-Agent": "ow-mod-db-readmes/1.0"}


def fetch_readme(url: str) -> str:
    resp = httpx.get(url, timeout=30.0, follow_redirects=True, headers=HEADERS)
    resp.raise_for_status()
    text = resp.text
    if len(text) > MAX_README_CHARS:
        raise ValueError(f"README 过大: {len(text)} chars")
    return text


def chunk_markdown(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """按段落边界把长文本切成 ≤max_chars 的块."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        if len(p) > max_chars:  # 单段超长:硬切
            for i in range(0, len(p), max_chars):
                chunks.append(p[i:i + max_chars])
            continue
        candidate = p if not current else current + "\n\n" + p
        if len(candidate) > max_chars:
            chunks.append(current)
            current = p
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_PLACEHOLDER = "⟦{}⟧"


def protect_markdown(text: str) -> tuple[str, list[str]]:
    """把代码块/表格/行内代码/图片/链接抽成占位符,翻译时结构不被破坏.

    返回 (保护后的文本, 占位符对应原文列表). 翻译后按序还原.
    """
    holders: list[str] = []

    def stash(block: str) -> str:
        idx = len(holders)
        holders.append(block)
        return _PLACEHOLDER.format(idx)

    out = text

    # 1) 围栏代码块(整体占位,含 ``` 行)
    parts = out.split("```")
    rebuilt = []
    for i, seg in enumerate(parts):
        if i % 2 == 1:                      # 代码块内容
            rebuilt.append(stash("```" + seg + "```"))
        else:
            rebuilt.append(seg)
    out = "".join(rebuilt)

    # 2) 表格块(连续以 | 开头的行整体占位)
    def table_keep(m: "re.Match") -> str:
        return stash(m.group(0).rstrip())

    out = re.sub(r"(?m)^\|.*(?:\n\|.*)+", table_keep, out)

    # 3) 行内代码 / 图片 / 链接(先 code 后 image/link)
    def inline_keep(m: "re.Match") -> str:
        return stash(m.group(0))

    out = re.sub(r"`[^`\n]+`", inline_keep, out)
    out = re.sub(r"!?\[[^\]\n]*\]\([^)\n]*\)", inline_keep, out)

    return out, holders


def restore_markdown(translated: str, holders: list[str]) -> str:
    for idx, original in enumerate(holders):
        translated = translated.replace(_PLACEHOLDER.format(idx), original)
    return translated


def is_translatable(unique_name: str, license_spdx: str, denylist: list) -> tuple[bool, str]:
    """返回 (是否翻, 原因)."""
    if unique_name in denylist:
        return False, "作者列入 denylist"
    if not license_spdx or license_spdx == "none":
        return False, "无许可"
    if license_spdx not in PERMISSIVE_LICENSES:
        return False, f"许可 {license_spdx} 不在白名单"
    return True, "ok"


def translate_readmes(official: dict, licenses: dict, cache: dict, denylist: list,
                      ai_translate, *, at: str, max_workers: int = 4,
                      limit: int = 0, force: bool = False,
                      sleep=time.sleep) -> tuple[int, int, list[str]]:
    """返回 (新翻译数, 跳过数, 错误列表)."""
    candidates = []
    for mod in official.get("releases", []):
        un = mod.get("uniqueName", "")
        readme = mod.get("readme") or {}
        url = readme.get("downloadUrl")
        if not url:
            continue
        ok, reason = is_translatable(un, licenses.get(un, "none"), denylist)
        if not ok:
            continue
        # 按安装量降序,热门先翻(便于分批抽查)
        candidates.append((un, url, mod.get("installCount") or mod.get("downloadCount") or 0))
    candidates.sort(key=lambda c: c[2], reverse=True)
    if limit > 0:
        candidates = candidates[:limit]

    lock = threading.Lock()
    state = {"new": 0, "skipped": 0}
    errors: list[str] = []

    def work(un_url):
        un, url = un_url[:2]
        try:
            en = fetch_readme(url)
        except Exception as e:
            with lock:
                errors.append(f"{un}: 抓取失败 {e}")
            return
        digest = sha256_text(en)
        entry = cache.get(un)
        if not force and entry and entry.get("sha") == digest:
            with lock:
                state["skipped"] += 1
            return
        protected, holders = protect_markdown(en)   # 代码/表格/链接先抽离防翻坏
        chunks = chunk_markdown(protected)
        translated = []
        for chunk in chunks:
            for attempt in range(3):
                try:
                    translated.append(ai_translate(chunk))
                    break
                except ai_client.AIError as e:
                    if attempt == 2:
                        with lock:
                            errors.append(f"{un}: 翻译失败 {e}")
                        return
                    sleep(2 * (2 ** attempt))
        zh = restore_markdown("\n\n".join(translated), holders)
        with lock:
            cache[un] = {"sha": digest, "zh": zh, "at": at}
            state["new"] += 1

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(work, candidates))
    return state["new"], state["skipped"], errors


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate licensed mods' READMEs")
    parser.add_argument("--lang", default="zh_cn", help="语言目录代码,如 zh_cn/ja")
    parser.add_argument("--official", default="source/official.json")
    parser.add_argument("--licenses", default="source/license_cache.json")
    parser.add_argument("--readmes", default=None)
    parser.add_argument("--glossary", default=None)
    parser.add_argument("--denylist", default="source/readme_denylist.json")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="本次最多翻译的 README 数(分批上线用)")
    parser.add_argument("--force", action="store_true",
                        help="忽略内容哈希,全部重翻(翻译策略升级后使用)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run:
        missing = [k for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL")
                   if not os.environ.get(k)]
        if missing:
            print(f"缺少环境变量: {', '.join(missing)}")
            raise SystemExit(1)

    lang = args.lang
    readmes_path = Path(args.readmes) if args.readmes else lang_file("readmes", lang)
    glossary_path = Path(args.glossary) if args.glossary else lang_file("glossary", lang)
    official = load_json(Path(args.official))
    licenses = load_json(Path(args.licenses))
    cache = load_json(readmes_path)
    denylist = json.loads(Path(args.denylist).read_text(encoding="utf-8")) \
        if Path(args.denylist).exists() else []

    # 白名单统计
    translatable = sum(1 for m in official.get("releases", [])
                       if is_translatable(m.get("uniqueName", ""),
                                          licenses.get(m.get("uniqueName", ""), "none"),
                                          denylist)[0])
    print(f"白名单内可翻译 README: {translatable} 个;已有缓存: {len(cache)} 个")

    if args.dry_run:
        return

    glossary = load_json(glossary_path)

    def ai_translate(text: str) -> str:
        # README 也注入术语表(否则专有名词会被随意翻译,如 外星迷航)
        return ai_client.translate_with_ai(
            text, glossary,
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["OPENAI_API_KEY"],
            model=os.environ["OPENAI_MODEL"],
            target_lang=LANG_NAME.get(lang, "简体中文"),
        )

    new, skipped, errors = translate_readmes(
        official, licenses, cache, denylist, ai_translate,
        at=_now_iso(), max_workers=args.concurrency, limit=args.limit, force=args.force,
    )
    save_json(readmes_path, cache)
    print(f"README 翻译完成: 新翻 {new}, 未变跳过 {skipped}, 失败 {len(errors)}")
    for e in errors[:10]:
        print(f"  ERR {e}")


if __name__ == "__main__":
    main()
