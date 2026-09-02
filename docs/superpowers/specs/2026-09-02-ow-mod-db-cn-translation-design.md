# 星际拓荒 MOD 数据库汉化方案设计

日期: 2026-09-02
状态: 已获用户批准

## 背景与目标

官方 MOD 数据库 `https://ow-mods.github.io/ow-mod-db/database.json` 持续更新(当前 413 个 MOD,最近更新 2026-09-01),但其中 `name`、`description`、`latestReleaseDescription` 均为英文,中文玩家阅读困难。

**短期目标**: 建立一条自动流水线,定时同步官方数据库,用 AI API 把 MOD 名称、简介、更新说明翻译成中文,并产出:
1. 一个中文 MOD 数据库网站(GitHub Pages,含列表/搜索/筛选/详情页)
2. 一份可替换的 `database.json`(玩家在 Outer Wilds Mod Manager 里把数据库网址改成我们的,即可在游戏内看到中文简介)

**远期目标**: 成立星际拓荒 MOD 汉化团队,人工翻译逐步覆盖并优先于机器翻译。

## 已确认的决策

| 项目 | 决定 |
|---|---|
| 交付物 | 中文网站 + 可替换 database.json,两者都要 |
| 部署 | GitHub Pages,单仓库全自动流水线 |
| 翻译方式 | AI API(OpenAI 兼容接口,`base_url` + `key` 可配置,供应商未定) |
| 自动化 | GitHub Actions 定时同步 + 翻译 + 部署 |
| 翻译字段 | `name`、`description`、`latestReleaseDescription` |
| 不翻译字段 | `author`、`authorDisplay` 等其余字段保持原样 |
| 专有名词 | 术语表 `glossary.json`,AI 翻译时遵守;表本身实时更新(团队随时提交,下次 CI 生效) |
| 人工覆盖 | `human_translations.json`,优先级高于 AI 翻译 |
| 网站功能 | 完整站: 列表页(搜索、分类筛选)+ 详情页 |

## 架构总览

单仓库 `ow-mod-db`,两个分支:

- `main` 分支: 源码(脚本、术语表、翻译缓存、网站源码)
- `gh-pages` 分支: 产物(中文 `database.json` + 静态网站)

GitHub Actions workflow `sync-translate.yml` 每 6 小时(可配置)运行一次,也可手动触发。

```
官方 ow-mods.github.io/ow-mod-db/database.json
  ↓ sync.py — 下载 + 差异检测
新增/变更字段 (uniqueName + 字段名)
  ↓ translate.py — 查 human 覆盖 → 未命中则带 glossary 调 AI
translations.json 缓存
  ↓ build.py — 合并官方数据 + 翻译
中文 database.json (结构与原版完全一致) + 网站数据 JSON
  ↓ 部署到 gh-pages
https://<用户>.github.io/ow-mod-db/
  ├─ / 网站(列表/搜索/筛选/详情页)
  └─ /database.json (OWMM 改数据库网址即用)
```

## 仓库结构

```
ow-mod-db/
├── .github/workflows/sync-translate.yml   # 定时(每6小时)+ 手动触发
├── scripts/
│   ├── sync.py          # 下载官方数据库,与翻译缓存对比出差异
│   ├── translate.py     # 翻译: human 覆盖 → glossary+AI → 写缓存
│   ├── build.py         # 生成中文 database.json + 网站数据
│   └── test/            # 单元测试
├── source/
│   ├── glossary.json            # 专有名词表(英文→中文)
│   ├── human_translations.json  # 人工覆盖(远期汉化团队维护)
│   └── translations.json        # AI 翻译缓存(只翻增量)
├── site/                        # 网站源码(静态)
└── docs/superpowers/specs/      # 设计文档
```

## 组件设计

### 1. sync.py — 同步与差异检测

- 下载 `https://ow-mods.github.io/ow-mod-db/database.json`
- 与 `translations.json` 缓存对比: 对每个 `releases[]` / `alphaReleases[]` 条目,按 `uniqueName` 找出 `name`、`description`、`latestReleaseDescription` 中内容变化(与原文缓存比较)的字段
- 输出待翻译字段清单;无变化则跳过翻译(省 API 费用)
- 官方数据库不可用时: 报错退出,不破坏现有产物

### 2. translate.py — 翻译

翻译优先级:
1. `human_translations.json` 中 `uniqueName.字段` 命中 → 直接用,不调 API
2. 未命中 → 构造 prompt,内容包含:
   - 待翻译的英文原文
   - `glossary.json` 全部术语(要求专有名词按术语表翻译,表外专有名词保留原文或音译)
   - 要求: 保持语气自然、保留 Markdown/换行/占位符、`<` `>` 等符号不被破坏
3. 调用 OpenAI 兼容 API(`OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL` 从环境变量读取;供应商定好后只需改 Secret)
4. 结果写入 `translations.json`(键: `uniqueName`,值: 原文+译文+翻译时间)

错误处理:
- AI 调用失败 → 指数退避重试 3 次,仍失败则该字段保持英文并在运行日志标注,不阻塞整体发布
- 空字段 / 纯空白 → 不翻译

### 3. build.py — 生成产物

- 合并官方数据与翻译: 输出中文 `database.json`,结构与官方完全一致(OWMM 兼容),仅替换 `name`/`description`/`latestReleaseDescription`;`author` 等字段原样保留
- 同时输出网站数据(列表项 + 详情页内容),写入 `site/data/`
- dry-run 模式: `--dry-run` 不调 API、不部署,本地验证用

### 4. 术语表 glossary.json(实时更新)

格式:

```json
{
  "Nomai": "挪麦",
  "Outer Wilds": "星际拓荒",
  "Hearthian": "哈斯人",
  "OWML": "OWML"
}
```

- 普通仓库文件,汉化团队随时新增/修改词条,提交后下次 CI 自动生效,无需改代码
- 新 MOD 出现的新专有名词,由团队成员补充;AI 未在表中找到的专有名词要求保留原文

### 5. 人工覆盖 human_translations.json(远期团队)

格式:

```json
{
  "Alek.OWML": {
    "description": "人工精校版简介……"
  }
}
```

- 优先级最高;团队逐步提交人工翻译,自动覆盖机器翻译

### 6. 网站 site/(完整站)

- 纯静态,原生 HTML/CSS/JS,无构建框架,客户端渲染: 页面 fetch `data/` 下的 JSON 动态渲染列表与详情
- 数据文件由 `build.py` 生成并随网站一起部署
- 列表页: 全部 MOD,中文名 + 中文简介摘要 + 作者(英文)+ 下载量,支持按名称搜索、按 `tags` 分类筛选
- 详情页: 完整中文简介、更新说明、作者、下载链接(指向官方 `downloadUrl`)、仓库链接
- 语言: 界面中文;作者名保持英文(已确认不翻)

## GitHub Actions 流水线

`sync-translate.yml`(schedule: cron `0 */6 * * *`,workflow_dispatch 手动):

1. checkout main
2. 安装 Python 依赖(Python 3.11+,`requirements.txt`)
3. 运行单元测试
4. `sync.py` → `translate.py`(需要 Secret 注入环境变量)→ `build.py`
5. 有变化: 提交 `translations.json` 等缓存回 main
6. 部署产物到 gh-pages(如 `peaceiris/actions-gh-pages` 或直接 push)
7. 失败告警: workflow 失败时以 issue/邮件提醒(可选,后续加)

GitHub Secrets:
- `OPENAI_BASE_URL`(OpenAI 兼容接口地址)
- `OPENAI_API_KEY`
- `OPENAI_MODEL`(模型名,如 deepseek-chat)

## 错误处理汇总

| 场景 | 处理 |
|---|---|
| AI API 失败 | 重试 3 次(指数退避),仍失败则该字段保持英文 + 日志标注 |
| 官方数据库下载失败 | 本次同步中止,现有产物不受影响 |
| 某 MOD 翻译失败 | 单条跳过,不阻塞其他 MOD 和发布 |
| 空字段 | 不翻译 |
| 翻译缓存无变化 | 跳过翻译步骤,零 API 消耗 |

## 测试

- 单元测试(scripts/test/):
  - 差异检测: 新增 mod / 字段变更 / 无变化 三种情况
  - 合并逻辑: 输出 database.json 结构与官方一致(字段齐全)
  - 术语表注入: prompt 构造包含 glossary
  - human 覆盖优先级: 命中时未调用 API(mock)
  - dry-run: 不产生真实 API 调用
- CI 中先跑测试,通过才部署

## 明确不做(现阶段)

- 不做每次访问实时翻译(Serverless)——成本不可控,已否决
- 不做 MOD 文件本体汉化(那是汉化团队的工作,不在本系统内)
- 不翻译 `author`/`authorDisplay`/`tags`
- 不做登录、评论、投稿等社区功能
- 不自动生成新专有名词条目(由团队人工维护,保证质量)

## 远期扩展

- 汉化团队成立后,以 PR 形式向 `human_translations.json` 提交人工翻译
- 术语表随团队翻译经验持续扩充
- 网站可后续加"翻译贡献"入口
