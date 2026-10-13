"""OG 分享卡片字体子集检查: 新 mod 名出现新字符时需重跑 scripts/build_og_font.py。"""

import json
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
FONT = ROOT / "assets" / "NotoSansSC-og.otf"


def _official() -> dict:
    return json.loads((ROOT / "source" / "official.json").read_text(encoding="utf-8"))


def _zh_translations() -> dict:
    return json.loads((ROOT / "source" / "zh_cn" / "translations.json").read_text(encoding="utf-8"))


def test_og_font_subset_exists():
    assert FONT.exists(), "字体子集缺失: 运行 python scripts/build_og_font.py"


def test_og_font_covers_names_and_authors():
    cmap = TTFont(FONT, lazy=True).getBestCmap()
    zh = _zh_translations()
    missing: set[str] = set()
    official = _official()
    for mod in official["releases"] + official.get("alphaReleases", []):
        uid = mod.get("uniqueName", "")
        texts = (
            str(mod.get("name") or ""),
            str(mod.get("authorDisplay") or mod.get("author") or ""),
            str((zh.get(uid) or {}).get("name", {}).get("zh") or ""),
        )
        for text in texts:
            missing |= {ch for ch in text if ch != "\n" and ord(ch) not in cmap}
    assert not missing, f"字体子集缺字符: {''.join(sorted(missing))} — 重跑 scripts/build_og_font.py"
