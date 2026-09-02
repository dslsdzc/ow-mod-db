# source/ 目录说明(维护向导)

本目录是流水线的"状态与人工输入区"。**人工维护的文件**只有三个,其余全部由 CI 自动生成,无需(也不建议)手动编辑。

## 人工维护(汉化团队用)

### glossary.json —— 术语表
AI 翻译必须遵守的术语对照,分两节:

- `terms`: 地点/概念/设施等,要求**直接译为中文**
  ```json
  { "Quantum Moon": "量子卫星", "Warp Core": "跃迁核心" }
  ```
- `characters`: 角色名,要求**首次出现用「原名(中文名)」格式**,同段后续只用中文
  ```json
  { "Hornfels": "霍恩费斯", "Solanum": "所莱内姆" }
  ```

**更新方式**: 直接改文件并推送。流水线会自动: 值变更的词条对已有译文做零成本替换; 新增词条只重译原文含该词的字段。无需手动触发。

### human_translations.json —— 人工翻译覆盖
格式 `{ "uniqueName": { "字段": "译文" } }`,优先级高于 AI:

```json
{ "xen.NewHorizons": { "name": "新地平线" } }
```

**更新方式**: 新增/修改后推送即可 —— 自动覆盖已缓存的 AI 译文(机器永不覆盖人工)。

### readme_denylist.json —— 作者下架名单
数组,列入的 uniqueName 其 README 不会被翻译(尊重作者意愿):
```json
["Some.AuthorMod"]
```

## 自动生成(勿手改)

| 文件 | 内容 | 何时重写 |
|---|---|---|
| `official.json` | 官方数据库快照 | 每次同步 |
| `pending.json` | 待翻译清单(增量) | 每次同步 |
| `translations.json` | MOD 元数据译文缓存(en/zh/at) | 每次翻译 |
| `readmes.json` | README 中文缓存(sha/zh/at) | README 内容变化时 |
| `license_cache.json` | 各 mod 仓库许可扫描结果 | 新 mod 出现时 |
| `last_glossary.json` | 上次生效的术语表快照(变更检测用) | 每次成功翻译后 |

## 许可说明

- `DATA-LICENSE` — 数据产物(MIT, 上游同为 MIT)
- `GLOSSARY-LICENSE` — 术语表(事实性对照, 无独立版权主张)

## 相关链接

- 全流程说明与玩家用法: 仓库根目录 [README](../README.md)
- 本地调试命令: `python scripts/sync.py` → `translate.py` → `readmes.py` → `build.py`
