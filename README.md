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

## 复刻部署(给想自建镜像的人)

1. 克隆本仓库并推送到你自己的 GitHub
2. 仓库 Settings → Pages → Source 选择 `gh-pages` 分支
3. 仓库 Settings → Secrets and variables → Actions,添加:
   - `OPENAI_BASE_URL` — OpenAI 兼容接口地址(如 `https://api.deepseek.com/v1`)
   - `OPENAI_API_KEY` — API Key
   - `OPENAI_MODEL` — 模型名(如 `deepseek-v4-flash`;DeepSeek 旧名 `deepseek-chat`/`deepseek-reasoner` 已于 2026-07-24 停用,不能再填)
4. 手动触发一次 Actions 的 `sync-translate` 工作流,或直接推送任意 source/ 下文件
5. 站点与数据库网址中的用户名换成你自己的 GitHub 用户名即可
6. (可选)启用仓库 Discussions 并在各详情页评论区生效

## 维护

详细说明见 [`source/README.md`](source/README.md) —— 里面标注了哪些文件**人工可改**、哪些**自动生成勿动**。

### 人工翻译覆盖 `source/human_translations.json`
人工精校优先于 AI。**新增或修改条目后推送即可,自动覆盖已缓存的 AI 译文**,格式:

```json
{
  "xen.NewHorizons": { "name": "新地平线" },
  "Alek.OWML": { "description": "人工精校版简介" }
}
```

### 专有名词表 `source/glossary.json`
- `terms`: 地点/概念等,直接译为中文(如 `Quantum Moon → 量子卫星`)
- `characters`: 角色名,首次出现用「原名(中文名)」格式(如 `Hornfels(霍恩费斯)`),同段之后只写中文

术语表更新后**无需全量重翻**: 值变更走零成本确定性替换;新增词条只重译命中字段;人工翻译永不被机器覆盖。

## 许可(分层)

| 内容 | 许可 | 许可文件 |
|---|---|---|
| 网站与代码(`scripts/`、`site/`、CI 配置)| **GPL-3.0** | `LICENSE` |
| 数据产物(`source/official.json`、翻译缓存、`database.json` 等)| **MIT** | `source/DATA-LICENSE` |
| 术语表 `source/glossary.json` 等 | 事实性对照,**无独立版权主张**(译名版权归官方/原作者) | `source/GLOSSARY-LICENSE` |
| 上游数据 | MIT © ow-mods | 官方仓库 |
| MOD 元数据/README | 版权归各自作者 | 按各仓库许可处理,本站仅展示与按许可翻译 |

## 本地运行(调试)

```bash
pip install -r requirements.txt
python scripts/sync.py                      # 下载官方库 + 生成待翻译清单
python scripts/translate.py --dry-run       # 只统计,不调 API
python scripts/translate.py                 # 真实翻译(需环境变量)
python scripts/readmes.py --dry-run         # README 翻译统计
python scripts/build.py                     # 生成 dist/
python -m http.server 8000 --directory dist # 预览网站
python -m pytest scripts/test -q            # 测试
```

## 测试

`python -m pytest scripts/test -q`
