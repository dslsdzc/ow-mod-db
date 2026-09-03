# 星际拓荒 MOD 数据库(中文镜像)

自动同步 [官方 MOD 数据库](https://ow-mods.github.io/ow-mod-db/database.json),用 AI 将 MOD 名称、简介、更新说明与 README 汉化为简体中文,并按中文社区既有译名逐步人工定名。

- **中文网站**: https://dslsdzc.github.io/ow-mod-db/
  - 首页三栏(热门 / 热门新 / 最近更新)与官方站点同构
  - 全部 MOD 列表:搜索、排序、tag 筛选
  - 详情页:中文简介与更新说明、README(中文优先,可切换英文原文)、许可白名单翻译、一键安装(需 OWMM)、讨论区(giscus)
- **可替换 database.json**: 在 Outer Wilds Mod Manager 中把数据库网址改为
  `https://dslsdzc.github.io/ow-mod-db/database.json`,游戏内即可看到中文简介

## 工作方式

- 每 30 分钟轮询一次上游官方数据库:**只有上游真的更新了**才会触发翻译与部署(无变化时提前退出)
- 术语表 / 人工翻译 / 前端代码推送后自动全流程部署
- 首次全量翻译,之后只翻译新增/变更内容;术语表变更走"确定性替换 + 命中字段定向重译",不整库重翻
- README 仅翻译**开放许可**(MIT 等白名单)仓库,尊重无许可/传染性许可作者的意愿(即时翻译按钮仅供个人浏览,不保存)

## 维护

详细说明见 [`source/README.md`](source/README.md) —— 里面标注了哪些文件**人工可改**、哪些**自动生成勿动**。

### 人工翻译覆盖 `source/zh_cn/human_translations.json`(ja 为 `source/ja/human_translations.json`)
人工精校优先于 AI。**新增或修改条目后推送即可,自动覆盖已缓存的 AI 译文**,格式:

```json
{
  "xen.NewHorizons": { "name": "新地平线" },
  "Alek.OWML": { "description": "人工精校版简介" }
}
```

### 专有名词表 `source/zh_cn/glossary.json`(ja 为 `source/ja/glossary.json`)
- `terms`: 地点/概念等,直接译为中文(如 `Quantum Moon → 量子卫星`)
- `characters`: 角色名,首次出现用「原名(中文名)」格式(如 `Hornfels(霍恩费斯)`),同段之后只写中文

术语表更新后**无需全量重翻**: 值变更走零成本确定性替换;新增词条只重译命中字段;人工翻译永不被机器覆盖。

## 多语言

数据与译文案卷按语言目录组织在 `source/` 下;目录代码即各脚本的 `--lang` 参数,也是站点数据目录代码(zh_cn 数据在根 `data/`,其余在 `data/<code>/`)。

| 目录代码 | 显示语言 | 说明 |
|---|---|---|
| `zh_cn` | 简体中文 | 默认语言;`data/` 根路径不变,URL 与迁移前一致 |
| `ja` | 日本語 | 增量语言;ja 数据缺失/未翻译时站点回退官方英文原文,不空白 |

- 界面文案(按钮/栏目等)按站点语言字典(site/js/i18n.js,`ui-lang`)显示,与数据语言联动
- 人工维护与自动生成的译文案卷均为**每语言一份**:如术语表 `source/zh_cn/glossary.json`、`source/ja/glossary.json`
- `source/official.json`、`source/license_cache.json`、`source/readme_denylist.json` 等与语言无关,仍留在 `source/` 根目录

### 新增语言

1. 建 `source/<code>/` 目录,放入与 zh_cn 同构的空种子(translations/readmes/releases_cache/human_translations/glossary 等为 `{}`;`pending.json` 不用手建,`sync.py --lang <code>` 会生成);`jams.json` 与 `jam_content.json`(Jam 届次与页面内容,**每语言一份、人工策展**,可先复制 zh_cn 再译;缺失时站点按默认渲染)
2. 填充该语言术语词典 `source/<code>/glossary.json`(空词典 = 全部交给 AI 直译)
3. 翻译缓存映射表 `source/<code>/translations.json` 由流水线自动生成;人工精校走 `source/<code>/human_translations.json`,优先级高于 AI
4. 代码侧登记两处,漏一处则新语言不生效:`scripts/build.py` 的 `LANGS`(现 `["zh_cn","ja","en"]`;末位 `en` 为官方原文回退数据,勿删)追加该目录代码;站点侧登记显示语言与数据目录代码及切换器选项(见 site/js/i18n.js 的词典、语言切换器与 `LANG_DIR` 映射)——否则 `dist/` 不产出新语言目录、切换器也不可选
5. 在 CI 的 `workflow_dispatch` 选该 `lang` 跑通一轮验证

### ja 术语取证要求

日本語术语词典**必须人工从游戏官方日文版逐条取证后填充**,不得依赖 AI 或机翻猜测——官方日文译名常与字面翻译不同(如 Nomai → ノマイ)。填充后按术语表更新规则自动重译命中字段。

## 许可(分层)

| 内容 | 许可 | 许可文件 |
|---|---|---|
| 全部代码(`scripts/`、`site/`、`.github/`)| **GPL-3.0**(copyleft:允许使用与修改,衍生作品必须同样开源) | `LICENSE` |
| 数据产物(`source/official.json`、翻译缓存、`database.json` 等)| **MIT** | `source/DATA-LICENSE` |
| 术语表 `source/zh_cn/glossary.json` 等(各语言目录同构,如 `source/ja/`) | 事实性对照,**无独立版权主张**(译名版权归官方/原作者) | `source/GLOSSARY-LICENSE` |
| 上游数据 | MIT © ow-mods | 官方仓库 |
| MOD 元数据/README | 版权归各自作者 | 按各仓库许可处理,本站仅展示与按许可翻译 |

## 本地运行(调试)

```bash
pip install -r requirements.txt
python scripts/sync.py                      # 下载官方库 + 生成待翻译清单
python scripts/translate.py --dry-run       # 只统计,不调 API
python scripts/translate.py                 # 真实翻译(需环境变量)
python scripts/readmes.py --dry-run         # README 翻译统计
python scripts/build.py                     # 生成 dist/(zh_cn 根路径 + 全部语言数据目录)
python -m http.server 8000 --directory dist # 预览网站
python -m pytest scripts/test -q            # 测试
```

以上命令默认操作 zh_cn 数据;对其它语言加 `--lang <code>`,例如 `--lang ja`:

```bash
python scripts/sync.py --lang ja            # 生成 source/ja/pending.json
python scripts/translate.py --lang ja --limit 20   # ja 试点:只翻译前 20 条
python scripts/readmes.py --lang ja --dry-run      # ja README 翻译统计
```

## 测试

`python -m pytest scripts/test -q`
