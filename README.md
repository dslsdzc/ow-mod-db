# 星际拓荒 MOD 数据库(汉化版)

自动同步 [官方 MOD 数据库](https://ow-mods.github.io/ow-mod-db/database.json),用 AI 将 MOD 名称、简介、更新说明汉化为简体中文,部署为:

- **中文网站**: 官方站点的翻译镜像(首页三栏/全部 MOD 列表/详情页,参照官方布局与配色)
- **可替换 database.json**: 在 Outer Wilds Mod Manager 中把数据库网址改为本仓库的 GitHub Pages 地址,游戏内即可看到中文简介

## 部署前准备(一次性)

1. 推送本仓库到 GitHub
2. 仓库 Settings → Pages → Source 选择 `gh-pages` 分支(首次部署后生效)
3. 仓库 Settings → Secrets and variables → Actions,添加:
   - `OPENAI_BASE_URL` — OpenAI 兼容接口地址(如 `https://api.deepseek.com/v1`)
   - `OPENAI_API_KEY` — API Key
   - `OPENAI_MODEL` — 模型名(如 `deepseek-v4-flash`;DeepSeek 旧名 `deepseek-chat`/`deepseek-reasoner` 已于 2026-07-24 停用,不能再填)
4. 手动触发一次 Actions 的 `sync-translate` 工作流验证

之后每 6 小时(UTC 0/6/12/18 点,即北京时间 8/14/20/2 点)自动同步翻译。首次运行会全量翻译,之后只翻译新增/变更的字段。

## 让玩家使用中文数据库

Mod Manager 设置 → Advanced → Database URL 改为:
`https://<你的用户名>.github.io/ow-mod-db/database.json`

## 维护

### 专有名词表 `source/glossary.json`
AI 翻译必须遵守的术语表,分两类。团队发现新专有名词直接加条目,提交后下次同步自动生效:

```json
{
  "terms": {
    "Nomai": "挪麦",
    "Quantum Moon": "量子卫星"
  },
  "characters": {
    "Hornfels": "霍恩费斯",
    "Solanum": "所莱内姆"
  }
}
```

- `terms`: 地点/概念等,**直接译为中文**(如 "Quantum Moon" → "量子卫星")
- `characters`: 角色名,**首次出现用「原名(中文名)」格式**(如 "Hornfels(霍恩费斯)"),同段之后只写中文

### 人工翻译覆盖 `source/human_translations.json`
人工精校优先于 AI,格式:

```json
{
  "Alek.OWML": {
    "description": "人工精校版简介"
  }
}
```

## 本地运行(调试)

```bash
pip install -r requirements.txt
python scripts/sync.py                      # 下载官方库 + 生成待翻译清单
python scripts/translate.py --dry-run       # 只统计,不调 API
python scripts/translate.py                 # 真实翻译(需环境变量)
python scripts/build.py                     # 生成 dist/
python -m http.server 8000 --directory dist # 预览网站
python -m pytest scripts/test -q            # 测试
```

## 测试

`python -m pytest scripts/test -q`
