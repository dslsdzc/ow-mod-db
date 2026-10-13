"""生成 OG 分享卡片所需的字体子集(输出到 assets/,提交进仓库,构建零系统依赖)。

字符集 = 全部 mod 标题/作者名 + 品牌与标签文案 + 全 ASCII。
新 mod 名称出现新字符时重跑本脚本; scripts/test/test_og_cards.py 会检测缺字并提醒。
"""

import json
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = "/usr/share/fonts/noto-cjk/NotoSansCJK-Medium.ttc"
SRC_INDEX = 2  # Noto Sans CJK SC Medium
OUT = ROOT / "assets" / "NotoSansSC-og.otf"

BRAND_TEXT = ("星际拓荒MOD数据库中文汉化简介一键安装作者版本"
              "·—…,。!?！？()（）：;；/+-")


def collect_chars() -> set[str]:
    chars = set(BRAND_TEXT) | {chr(i) for i in range(32, 127)}
    official = json.loads((ROOT / "source" / "official.json").read_text(encoding="utf-8"))
    zh = json.loads((ROOT / "source" / "zh_cn" / "translations.json").read_text(encoding="utf-8"))
    human = json.loads((ROOT / "source" / "zh_cn" / "human_translations.json").read_text(encoding="utf-8"))
    for mod in official["releases"] + official.get("alphaReleases", []):
        uid = mod.get("uniqueName", "")
        chars |= set(str(mod.get("name") or ""))
        chars |= set(str(mod.get("authorDisplay") or mod.get("author") or ""))
        chars |= set(str((zh.get(uid) or {}).get("name", {}).get("zh") or ""))
        chars |= set(str((human.get(uid) or {}).get("name") or ""))
    return chars


def main() -> None:
    chars = collect_chars()
    font = TTFont(SRC, fontNumber=SRC_INDEX)
    opts = subset.Options()
    subsetter = subset.Subsetter(options=opts)
    subsetter.populate(text="".join(sorted(chars)))
    subsetter.subset(font)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subset.save_font(font, str(OUT), opts)
    print(f"已生成 {OUT.relative_to(ROOT)}: {OUT.stat().st_size // 1024}KB, {len(chars)} 个字符")


if __name__ == "__main__":
    main()
