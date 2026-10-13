"""生成日本語术语取证清单(source/ja/glossary_todo.md)。

日本語术语必须人工从游戏官方日文版逐条取证后填入 source/ja/glossary.json,
不得依赖 AI 或机翻猜测(官方日文译名常与字面翻译不同,如 Nomai -> ノマイ)。
本脚本从 zh_cn 术语表提取全部待取证词条,按 ja 侧实际填写情况标记进度。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZH_GLOSSARY = ROOT / "source" / "zh_cn" / "glossary.json"
JA_GLOSSARY = ROOT / "source" / "ja" / "glossary.json"
OUT = ROOT / "source" / "ja" / "glossary_todo.md"


def render_todo(zh: dict, ja: dict) -> str:
    """zh_cn 术语表 -> 待取证清单 markdown(纯函数,便于测试)。"""
    total = done = 0
    body: list[str] = []
    sections = (
        ("terms", "terms(地点/概念,直接译为日文)"),
        ("characters", "characters(角色名,首次出现用「原名(译名)」格式)"),
    )
    for section, title in sections:
        src = zh.get(section) or {}
        filled = ja.get(section) or {}
        body += [f"## {title}", ""]
        if not src:
            body += ["(zh_cn 术语表本节为空)", ""]
            continue
        body += ["| 状态 | 原文 | 中文译名 | 日文官方译名(待填) |", "|---|---|---|---|"]
        for key, zh_name in src.items():
            total += 1
            ja_name = str(filled.get(key) or "").strip()
            if ja_name:
                done += 1
                body.append(f"| ✅ | {key} | {zh_name} | {ja_name} |")
            else:
                body.append(f"| ⬜ | {key} | {zh_name} | |")
        body.append("")
    header = [
        "# 日本語术语取证清单",
        "",
        f"进度: **{done} / {total}** 已取证",
        "",
        "> 由 `python scripts/ja_glossary_todo.py` 生成,重复运行即可刷新;**勿手改本文件**。",
        "> 日本語术语必须人工从游戏官方日文版逐条取证后填入 `source/ja/glossary.json`,",
        "> 不得依赖 AI 或机翻猜测(官方日文译名常与字面翻译不同,如 Nomai -> ノマイ)。",
        "> 填写后重跑本脚本,已取证词条会自动打勾。",
        "",
    ]
    return "\n".join(header + body) + "\n"


def main() -> None:
    zh = json.loads(ZH_GLOSSARY.read_text(encoding="utf-8"))
    ja = json.loads(JA_GLOSSARY.read_text(encoding="utf-8")) if JA_GLOSSARY.exists() else {}
    OUT.write_text(render_todo(zh, ja), encoding="utf-8")
    print(f"已生成 {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
