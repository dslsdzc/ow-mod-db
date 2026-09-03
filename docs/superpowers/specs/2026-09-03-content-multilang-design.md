# 内容多语言化(目录制)设计

日期: 2026-09-03
状态: 已获用户批准(方案 A + 四阶段)

## 背景与目标

站点内容(简介/README/版本说明/jam 文案/元数据)目前只有简体中文(源自英文官方库)。目标是按**语言目录**组织数据与流水线,使内容随界面语言切换;首增语言:日语(`ja`);现有中文数据迁移至 `zh_cn` 目录且行为不变。英文不建目录(官方快照即英文源)。OWMM 用 `database.json` 根路径保持为 zh_cn 版(URL 不变),多语言 OWMM 库输出列为后续独立项。

## 目录与语言代码

- 目录代码: `zh_cn`、`ja`
- 展示代码(html lang / localStorage `ui-lang` / 界面切换器): `zh-CN` ↔ `zh_cn`、`ja` ↔ `ja`;由 `LANG_DIR = { "zh-CN": "zh_cn", "ja": "ja" }` 映射
- 全局共享(非语言化): `source/official.json`(英文官方快照)、`source/license_cache.json`、`source/readme_denylist.json`
- 语言化文件(每语言目录一份): `glossary.json`、`translations.json`、`readmes.json`、`releases_cache.json`(译文部分;版本元数据仍取官方)、`human_translations.json`、`jams.json`、`jam_content.json`

## 数据布局

```
source/zh_cn/{glossary,translations,readmes,releases_cache,human_translations,jams,jam_content}.json
source/ja/    {同上}
```

迁移: git mv 现有 `source/*.json`(语言化文件)进 `source/zh_cn/`;`official.json`、`license_cache.json`、`readme_denylist.json` 留在 source/ 根。

## 脚本参数化

- `sync.py / translate.py / readmes.py / releases.py / build.py` 增加 `--lang`(默认 `zh_cn`)
- 语言化文件读写路径 = `source/<lang>/…`;`translations.json` 等默认值随 lang 变化
- 首次迁移后默认 zh_cn 行为与现线上一致(回归基准:全套测试 + 线上产物抽查)

## 网站取数

- 构建产物: `dist/data/<code>/mods.json`、`readmes.json`、`releases/<uid>.json`、`patches.json`、`licenses.json`、`jams.json`、`jam_content.json`
- 语言选择决定取哪套;缺失内容逐条回退: 该语言缺失 → 回退 `zh_cn` → 回退官方英文(翻译进度期不空白)
- OWMM: `dist/database.json` 仍为 zh_cn 版(保留原 URL);`dist/database.ja.json` 等另行输出(后续项,不在本 spec 落地)

## 翻译流水线(按语言)

- AI 请求 `--target-lang` + 该语言 `glossary.json` + 按语言的提示词规则(如 ja 角色名首次出现用 `原名(日本語名)`)
- ja 术语:先做官方日文版/日文社区用词取证再落库(同中文当初流程)
- 回填顺序: MOD 元数据 → README(沿用许可白名单/denylist)→ 版本说明 → jam 文案;分批 `--limit`/手动 dispatch 推进

## 测试与 CI

- 单元: `--lang` 路径、回退逻辑、语言映射
- 冒烟: 产物目录存在性与形状(每语言)、根 database.json 保持
- CI: workflow 默认 `--lang zh_cn`;`lang` dispatch 输入跑指定语言增量

## 明确不做(本 spec)

英文目录;OWMM 多语言切换与多语言 database 输出落地;ja 首批全量回填(先元数据试点);汉化团队协作流程(另立 spec)。
