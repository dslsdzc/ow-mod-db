# source/ 目录说明(维护向导)

本目录是流水线的"状态与人工输入区"。数据按语言分目录:`source/<lang>/` 内每语言一套译文案卷(`zh_cn` = 简体中文默认目录,`ja` = 日本語);与语言无关的共享文件(官方快照、许可扫描、作者下架名单等)留在 `source/` 根目录。`<lang>` 即各脚本的 `--lang` 参数(默认 `zh_cn`)。

## 人工维护(汉化团队用)

### `source/<lang>/glossary.json` —— 术语表(每语言一份)

AI 翻译必须遵守的术语对照,分两节:

- `terms`: 地点/概念/设施等,要求**直接译为该语言**
  ```json
  { "Quantum Moon": "量子卫星", "Warp Core": "跃迁核心" }
  ```
- `characters`: 角色名,要求**首次出现用「原名(译名)」格式**,同段后续只用译名
  ```json
  { "Hornfels": "霍恩费斯", "Solanum": "所莱内姆" }
  ```

**更新方式**: 直接改文件并推送。流水线会自动: 值变更的词条对已有译文做零成本替换; 新增词条只重译原文含该词的字段。无需手动触发。ja 等语言的值须**人工取证后填充**,不得凭 AI 猜测(见下文「多语言」)。

### `source/<lang>/human_translations.json` —— 人工翻译覆盖(每语言一份)

格式 `{ "uniqueName": { "字段": "译文" } }`,优先级高于 AI:

```json
{ "xen.NewHorizons": { "name": "新地平线" } }
```

**更新方式**: 新增/修改后推送即可 —— 自动覆盖已缓存的 AI 译文(机器永不覆盖人工)。

### `source/readme_denylist.json` —— 作者下架名单(根目录,全部语言共享)

数组,列入的 uniqueName 其 README 不会被翻译(尊重作者意愿):

```json
["Some.AuthorMod"]
```

## 自动生成(勿手改)

按语言目录 `source/<lang>/`,由对应脚本带 `--lang` 生成:

| 文件 | 内容 | 何时重写 |
|---|---|---|
| `<lang>/pending.json` | 待翻译清单(增量) | 每次同步 |
| `<lang>/translations.json` | MOD 元数据译文缓存(en/zh/at) | 每次翻译 |
| `<lang>/readmes.json` | README 译文缓存(sha/zh/at) | README 内容变化时 |
| `<lang>/releases_cache.json` | 版本发布说明缓存 | 版本抓取时 |
| `<lang>/last_glossary.json` | 上次生效的术语表快照(变更检测用) | 每次成功翻译后 |

根目录共享(语言无关,由 CI 生成):

| 文件 | 内容 | 何时重写 |
|---|---|---|
| `official.json` | 官方数据库快照 | 每次同步 |
| `license_cache.json` | 各 mod 仓库许可扫描结果 | 新 mod 出现时 |

## 多语言

- **目录代码与显示语言映射**: `zh_cn` ↔ 简体中文(默认)、`ja` ↔ 日本語。站点侧 zh_cn 数据在根 `data/`,其余语言在 `data/<lang>/`;ja 数据缺失/未翻译时回退官方英文原文,不空白。
- **新增语言**: ① 建 `source/<code>/` 目录,种子与 zh_cn 同构(空表即可;`pending.json` 不用手建,`sync.py --lang <code>` 自动生成);② 填该语言术语词典 `<code>/glossary.json`(空词典 = 全部交给 AI 直译);③ 译文映射表 `<code>/translations.json` 由流水线自动生成,人工精校走 `<code>/human_translations.json`;④ 站点侧登记显示语言与数据目录代码(site/js/i18n.js),并在 CI 的 workflow_dispatch 选该 `lang` 试跑验证。
- **ja 术语取证要求**: 日本語术语词典必须**人工从游戏官方日文版逐条取证后填充**,官方日文译名常与字面翻译不同,勿凭 AI/机翻猜测(如 Nomai → ノマイ)。

## 许可说明

- `DATA-LICENSE` — 数据产物(MIT, 上游同为 MIT)
- `GLOSSARY-LICENSE` — 术语表(事实性对照, 无独立版权主张)

## 相关链接

- 全流程说明与玩家用法: 仓库根目录 [README](../README.md)
- 本地调试命令(默认 zh_cn;其它语言加 `--lang <code>`): `python scripts/sync.py` → `translate.py` → `readmes.py` → `build.py`,示例:
  `python scripts/sync.py --lang ja && python scripts/translate.py --lang ja --limit 20`
