"""扫描各 mod 仓库许可证, 维护 source/license_cache.json(翻译白名单判定依据)。

数据源: GitHub REST /repos/{owner}/{repo} 的 license.spdx_id。
判定:
  - 无 repo 字段 / 404(仓库已删) / license 为 null -> "none"
  - "NOASSERTION"(有 LICENSE 文件但 GitHub 无法识别) 保守记录, 不进入翻译白名单
  - 其他 spdx_id 原样记录(白名单判断见 readmes.PERMISSIVE_LICENSES)

人工裁决: source/license_overrides.json 的 {uniqueName: spdx} 优先级最高,
用于修正误判(如确认 NOASSERTION 实为 MIT)。

默认只补扫缓存缺失的 mod(新 mod 出现时增量); --full 全量重扫并打印变化
(作者变更许可的场景)。查询失败(网络/限速)保留旧值并警告, 不视为"无许可"。

用法:
  GITHUB_TOKEN=xx python scripts/licenses.py            # 增量(缺失才扫)
  GITHUB_TOKEN=xx python scripts/licenses.py --full     # 全量(检测许可变更)
  python scripts/licenses.py --limit 5                  # 试扫少量
"""

import argparse
import os
import re
from pathlib import Path

import httpx

from translation_store import load_json, save_json

API = "https://api.github.com"
REPO_URL_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?$")


class RateLimited(Exception):
    """GitHub API 限速(403/429), 扫描应尽快停止。"""


def repo_slug(repo_url: str) -> str:
    """'https://github.com/owner/name' -> 'owner/name'; 无法解析返回空串。"""
    m = REPO_URL_RE.match((repo_url or "").strip())
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def fetch_license_spdx(slug: str, client: httpx.Client, token: str = "") -> str | None:
    """查询单个仓库许可; 请求失败/限速返回 None(与"确认无许可"区分)。"""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ow-mod-db-licenses/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = client.get(f"{API}/repos/{slug}", headers=headers)
    except httpx.HTTPError:
        return None
    if resp.status_code in (403, 429):
        raise RateLimited(slug)
    if resp.status_code == 404:
        return "none"
    if resp.status_code != 200:
        return None
    lic = (resp.json().get("license") or {}).get("spdx_id") or ""
    if not lic:
        return "none"
    if lic.upper() == "NOASSERTION":
        return "NOASSERTION"
    return lic


def scan(official: dict, cache: dict, overrides: dict, *, full: bool = False,
         limit: int = 0, token: str = "") -> tuple[dict, list[str]]:
    """增量/全量扫描; 返回 (更新后的缓存, 变更与警告列表)。"""
    notes: list[str] = []
    targets = []
    for mod in official.get("releases", []):
        uid = mod.get("uniqueName") or ""
        if uid and (full or uid not in cache):
            targets.append((uid, repo_slug(mod.get("repo") or "")))
    if limit:
        targets = targets[:limit]
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            for uid, slug in targets:
                if not slug:
                    new: str | None = "none"
                else:
                    new = fetch_license_spdx(slug, client, token)
                if new is None:
                    notes.append(f"{uid}: 查询失败, 保留旧值({cache.get(uid) or '未收录'})")
                    continue
                old = cache.get(uid)
                if old != new:
                    cache[uid] = new
                    notes.append(f"{uid}: {old or '(新收录)'} -> {new}")
    except RateLimited as e:
        notes.append(f"GitHub API 限速(扫描到 {e}), 本次提前结束; 其余条目留待下次")
    for uid, spdx in sorted(overrides.items()):
        if cache.get(uid) != spdx:
            notes.append(f"{uid}: 人工覆盖 {cache.get(uid) or '(无)'} -> {spdx}")
            cache[uid] = spdx
    return cache, notes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan mod repo licenses into license_cache.json")
    parser.add_argument("--official", default="source/official.json")
    parser.add_argument("--cache", default="source/license_cache.json")
    parser.add_argument("--overrides", default="source/license_overrides.json")
    parser.add_argument("--full", action="store_true", help="全量重扫(默认只补缺失)")
    parser.add_argument("--limit", type=int, default=0, help="最多扫描 N 个(调试用)")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    official = load_json(Path(args.official))
    cache = load_json(Path(args.cache))
    overrides_path = Path(args.overrides)
    overrides = load_json(overrides_path) if overrides_path.exists() else {}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not token:
        print("  警告: 未设置 GITHUB_TOKEN, GitHub API 限制 60 次/小时(大库可能被限速)")

    cache, notes = scan(official, cache, overrides, full=args.full, limit=args.limit, token=token)
    save_json(Path(args.cache), cache)
    for note in notes:
        print(f"  {note}")
    print(f"许可缓存: {len(cache)} 项, 本次变更 {len(notes)} 条")


if __name__ == "__main__":
    main()
