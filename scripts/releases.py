"""版本历史缓存: 按 repoUpdatedAt 增量抓取各 mod 仓库的 GitHub Releases.

数据源为 GitHub 公开 Releases API(与 ow-mods 服务无关).
缓存格式 source/releases_cache.json:
  { uniqueName: { "repoUpdatedAt": ..., "releases": [ {tag, name, date, body, zipUrl} ] } }

每仓库最多保留 MAX_RELEASES 条; body 超长截断.
"""

import argparse
import json
import os
import time
from pathlib import Path

import httpx

from translation_store import load_json, save_json

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official", default="source/official.json")
    parser.add_argument("--cache", default="source/releases_cache.json")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    official = load_json(Path(args.official))
    cache = load_json(Path(args.cache))
    token = os.environ.get("GITHUB_TOKEN", "")
    updated, skipped, errors = refresh_cache(official, cache, token,
                                             max_workers=args.concurrency)
    save_json(Path(args.cache), cache)
    print(f"版本缓存: 更新 {updated}, 跳过 {skipped}, 失败 {len(errors)}")
    for e in errors[:10]:
        print(f"  ERR {e}")


if __name__ == "__main__":
    main()
