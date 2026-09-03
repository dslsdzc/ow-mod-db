"""版本历史缓存: 按 repoUpdatedAt 增量抓取各 mod 仓库的 GitHub Releases.

数据源为 GitHub 公开 Releases API(与 ow-mods 服务无关).
缓存格式(语言目录下,默认 zh_cn) releases_cache.json:
  { uniqueName: { "repoUpdatedAt": ..., "releases": [ {tag, name, date, body, zipUrl} ] } }

每仓库最多保留 MAX_RELEASES 条; body 超长截断.
"""

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

import ai_client
import readmes
from translation_store import lang_file, load_json, save_json

MAX_RELEASES = 10
MAX_BODY_CHARS = 2500
API = "https://api.github.com"


def pick_zip_asset(assets: list) -> str:
    """优先 .zip 资产直链;没有则空(前端回退到 release 页面)."""
    for a in assets:
        url = (a.get("browser_download_url") or "").lower()
        if url.endswith(".zip"):
            return a.get("browser_download_url", "")
    return ""


TRANSLATE_BODIES_PER_MOD = 5   # 每个 mod 预翻最近几个版本的说明


def normalize_releases(payload: list, repo: str) -> list:
    out = []
    for rel in payload[:MAX_RELEASES]:
        tag = rel.get("tag_name") or ""
        body = (rel.get("body") or "").strip()[:MAX_BODY_CHARS]
        out.append({
            "tag": tag,
            "name": rel.get("name") or tag,
            "date": (rel.get("published_at") or "")[:10],
            "body": body,
            "bodyZh": "",          # 翻译后填充(许可白名单内)
            "zipUrl": pick_zip_asset(rel.get("assets") or []),
            "releaseUrl": f"https://github.com/{repo}/releases/tag/{tag}",
        })
    return out


def fetch_releases(repo: str, token: str = "") -> list:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = httpx.get(f"{API}/repos/{repo}/releases",
                     params={"per_page": MAX_RELEASES}, headers=headers, timeout=30.0)
    resp.raise_for_status()
    return normalize_releases(resp.json(), repo)


def refresh_cache(official: dict, cache: dict, token: str, max_workers: int = 1,
                  sleep=time.sleep) -> tuple[int, int, list[str]]:
    """对 repoUpdatedAt 变化的仓库抓取;返回 (更新数, 跳过数, 错误)."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    changed = []
    for mod in official.get("releases", []):
        un = mod.get("uniqueName", "")
        repo_url = (mod.get("repo") or "").strip()
        repo = repo_url.replace("https://github.com/", "").rstrip("/") if repo_url else ""
        if not repo:
            continue
        updated = mod.get("repoUpdatedAt", "")
        entry = cache.get(un) or {}
        if entry.get("repoUpdatedAt") == updated and "releases" in entry:
            continue
        changed.append((un, repo, updated))

    lock = threading.Lock()
    state = {"n": 0}
    errors: list[str] = []

    def work(item):
        un, repo, updated = item
        try:
            releases = fetch_releases(repo, token)
            with lock:
                cache[un] = {"repoUpdatedAt": updated, "releases": releases}
                state["n"] += 1
        except Exception as e:
            with lock:
                errors.append(f"{un}: {e}")

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(work, changed))
    return state["n"], len(changed) - state["n"], errors


def translate_bodies(cache: dict, licenses: dict, denylist: list, glossary: dict,
                     ai_translate, *, max_new: int = 0,
                     sleep=time.sleep) -> tuple[int, list[str]]:
    """为许可白名单内 mod 的最近 TRANSLATE_BODIES_PER_MOD 个版本补译 body.

    已有 bodyZh 的跳过;max_new=0 表示不限. 返回 (新译数, 错误).
    """
    lock = threading.Lock()
    state = {"n": 0}
    errors: list[str] = []

    def work(un_rels):
        un, rels = un_rels
        for rel in rels[:TRANSLATE_BODIES_PER_MOD]:
            body = rel.get("body") or ""
            if not body or rel.get("bodyZh"):
                continue
            protected, holders = readmes.protect_markdown(body)
            zh = ""
            for attempt in range(3):
                try:
                    zh = ai_translate(protected)
                    break
                except ai_client.AIError as e:
                    if attempt == 2:
                        with lock:
                            errors.append(f"{un} {rel.get('tag')}: {e}")
                        break
                    sleep(2 * (2 ** attempt))
            if not zh:
                continue
            zh = readmes.restore_markdown(zh, holders)
            with lock:
                rel["bodyZh"] = zh
                state["n"] += 1

    tasks = []
    for un, entry in cache.items():
        if un in denylist:
            continue
        if (licenses.get(un) or "none") not in readmes.PERMISSIVE_LICENSES:
            continue
        rels = (entry or {}).get("releases") or []
        if any(r.get("body") and not r.get("bodyZh") for r in rels[:TRANSLATE_BODIES_PER_MOD]):
            tasks.append((un, rels))
    if tasks:
        with ThreadPoolExecutor(max_workers=1) as ex:
            list(ex.map(work, tasks))
    return state["n"], errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="zh_cn", help="语言目录代码,如 zh_cn/ja")
    parser.add_argument("--official", default="source/official.json")
    parser.add_argument("--cache", default=None)
    parser.add_argument("--licenses", default="source/license_cache.json")
    parser.add_argument("--denylist", default="source/readme_denylist.json")
    parser.add_argument("--glossary", default=None)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--translate-bodies", action="store_true",
                        help="补译版本说明(许可白名单内,需 OPENAI_* 环境变量)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    lang = args.lang
    cache_path = Path(args.cache) if args.cache else lang_file("releases_cache", lang)
    glossary_path = Path(args.glossary) if args.glossary else lang_file("glossary", lang)
    official = load_json(Path(args.official))
    cache = load_json(cache_path)
    token = os.environ.get("GITHUB_TOKEN", "")
    updated, skipped, errors = refresh_cache(official, cache, token,
                                             max_workers=args.concurrency)

    if args.translate_bodies and not args.dry_run:
        missing = [k for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL")
                   if not os.environ.get(k)]
        if missing:
            print(f"缺少环境变量: {', '.join(missing)}")
            raise SystemExit(1)
        licenses = load_json(Path(args.licenses))
        denylist = json.loads(Path(args.denylist).read_text(encoding="utf-8")) \
            if Path(args.denylist).exists() else []
        glossary = load_json(glossary_path)

        def ai_translate(text: str) -> str:
            return ai_client.translate_with_ai(
                text, glossary,
                base_url=os.environ["OPENAI_BASE_URL"],
                api_key=os.environ["OPENAI_API_KEY"],
                model=os.environ["OPENAI_MODEL"],
            )

        new_bodies, body_errors = translate_bodies(cache, licenses, denylist, glossary,
                                                   ai_translate)
        print(f"版本说明翻译: 新译 {new_bodies}, 失败 {len(body_errors)}")
        errors += body_errors

    save_json(cache_path, cache)
    print(f"版本缓存: 更新 {updated}, 跳过 {skipped}, 失败 {len(errors)}")
    for e in errors[:10]:
        print(f"  ERR {e}")


if __name__ == "__main__":
    main()
