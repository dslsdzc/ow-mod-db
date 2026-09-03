# 内容多语言化(目录制) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 MOD 元数据/README/版本说明/jam 文案按 `source/<lang>/` 目录组织,流水线与网站支持 `--lang`/语言目录取数(默认 zh_cn 行为不变),并为日语 `ja` 建立目录与首批试点。

**Architecture:** ① git mv 现有语言化数据到 `source/zh_cn/`;② 各脚本 `--lang` 参数化,默认 `zh_cn`;③ build 产出保留根路径(zh_cn)并在 `dist/data/<code>/` 输出其它语言,网站取数按 `LANG_DIR_CODE` 路由+回退链(所选→zh_cn→官方 en);④ ja 目录与试点翻译;⑤ CI 与测试覆盖。

**Tech Stack:** Python 3.11 + pytest;原生 JS;GitHub Actions。

## Global Constraints

- 目录代码 `zh_cn`、`ja`;展示代码映射 `zh-CN↔zh_cn`、`ja↔ja`(i18n.js 内 `LANG_DIR`)
- 全局共享文件留在 source/ 根:`official.json`、`license_cache.json`、`readme_denylist.json`
- 语言化文件于 `source/<lang>/`:`glossary/translations/readmes/releases_cache/human_translations/jams/jam_content.json`
- 默认 `--lang zh_cn` 行为必须与迁移前一致(回归 = 全套测试 + 产物抽查)
- `dist/database.json` 恒为 zh_cn 版;网站数据:zh_cn → `data/`,其它语言 → `data/<code>/`
- 回退链: 所选语言缺失 → `zh_cn` → 官方英文(站点额外产出 `data/en/`)
- AI 提示目标语言按 `--lang` 映射(zh_cn→简体中文,ja→日本語)
- 测试从根目录 `python -m pytest scripts/test -q`

---

### Task 1: 迁移到 zh_cn 目录 + 路径解析助手

**Files:**
- Modify: `scripts/translation_store.py`
- Modify: `scripts/sync.py`、`scripts/translate.py`、`scripts/readmes.py`、`scripts/releases.py`、`scripts/build.py`(默认参数改为按 `--lang` 解析)
- Move: `source/glossary.json`、`source/translations.json`、`source/readmes.json`、`source/releases_cache.json`、`source/human_translations.json`、`source/jams.json`、`source/jam_content.json` → `source/zh_cn/`
- Keep: `source/official.json`、`source/license_cache.json`、`source/readme_denylist.json`

**Interfaces:**
- `translation_store` 新增:
  - `LANG_DEFAULT = "zh_cn"`
  - `lang_file(kind: str, lang: str = LANG_DEFAULT) -> Path` → `Path("source")/lang/f"{kind}.json"`
  - `site_data_dir(lang: str) -> str` → zh_cn 返回 `"data"`,其它返回 `f"data/{lang}"`
- 所有脚本新增 `--lang`(default `"zh_cn"`),语言化参数默认值改为 `None`,解析后赋 `lang_file(kind, args.lang)`;全局文件默认不变。

- [ ] **Step 1: git mv 语言化文件**

```bash
mkdir -p source/zh_cn
for f in glossary translations readmes releases_cache human_translations jams jam_content; do
  git mv source/$f.json source/zh_cn/$f.json
done
git status --short
```
Expected: 7 renamed;`source/official.json`、`license_cache.json`、`readme_denylist.json` 仍在根。

- [ ] **Step 2: 写失败测试**

`scripts/test/test_translation_store.py` 追加:
```python
from translation_store import LANG_DEFAULT, lang_file, site_data_dir

def test_lang_file_paths():
    assert str(lang_file("glossary")) == "source/zh_cn/glossary.json"
    assert str(lang_file("translations", "ja")) == "source/ja/translations.json"
    assert LANG_DEFAULT == "zh_cn"

def test_site_data_dir():
    assert site_data_dir("zh_cn") == "data"
    assert site_data_dir("ja") == "data/ja"
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest scripts/test/test_translation_store.py -q`
Expected: FAIL — 属性不存在

- [ ] **Step 4: 实现助手**

`scripts/translation_store.py` 末尾追加:
```python
LANG_DEFAULT = "zh_cn"


def lang_file(kind: str, lang: str = LANG_DEFAULT) -> Path:
    """语言化 JSON 的路径: source/<lang>/<kind>.json"""
    return Path("source") / lang / f"{kind}.json"


def site_data_dir(lang: str) -> str:
    """网站数据目录: zh_cn 用根 data/,其它语言 data/<code>/"""
    return "data" if lang == "zh_cn" else f"data/{lang}"
```

- [ ] **Step 5: 各脚本 `--lang` 与解析**

对 `sync.py / translate.py / readmes.py / releases.py / build.py` 做同一模式(以 translate.py 为例,其余类推):

在 argparse 参数区加入:
```python
    parser.add_argument("--lang", default="zh_cn", help="语言目录代码,如 zh_cn/ja")
```
语言化默认参数改为 `default=None`,解析后:
```python
    lang = args.lang
    pending_path = Path(args.pending) if args.pending else lang_file("pending", lang)
    translations_path = Path(args.translations) if args.translations else lang_file("translations", lang)
    human_path = Path(args.human) if args.human else lang_file("human_translations", lang)
    glossary_path = Path(args.glossary) if args.glossary else lang_file("glossary", lang)
    last_glossary_path = Path(args.last_glossary) if args.last_glossary else lang_file("last_glossary", lang)
```
并全部用这些局部变量替换原 `Path(args.…)` 用法(含 save 处)。

- `sync.py`:`--translations/--out/--save-official`(official 留在 `source/official.json`;`--out` pending 走 `lang_file("pending", lang)`)
- `readmes.py`:`--readmes/--glossary` 语言化;`--licenses/--denylist` 保持根默认
- `releases.py`:`--cache` → `lang_file("releases_cache", lang)`;`--licenses/--denylist/--glossary` 中 licenses/denylist 保持根,glossary 语言化
- `build.py`:`--translations/--readmes/--licenses/--releases/--patches/--jams/--jam-content` 中 translations/readmes/releases/patches? patches 为人工注册表语言无关(保持根)依据 spec(patches 未列入语言化清单——保持根);licenses 根;glossary 不需要;`--jams/--jam-content` 语言化;`--official` 根
  简化:`build.py` 语言化 = translations/readmes/releases_cache/jams/jam_content;并读 `--lang` 供产物目录。

- [ ] **Step 6: 修 tests 默认路径**

把测试中依赖旧根路径的 fixture 调用改为显式传 `--translations`/路径或使用 `lang_file`,使全套测试对默认 zh_cn 通过:

```bash
python -m pytest scripts/test -q
```
Expected: 全绿(原先 91 + 新增 2);无测试引用 source/translations.json 等根路径常量(保留 conftest 不变)。

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "refactor: 语言化数据迁移 source/zh_cn + --lang 路径助手(默认 zh_cn 行为不变)"
```

---

### Task 2: build 产物多目录 + 官方英文数据

**Files:**
- Modify: `scripts/build.py`
- Modify: `scripts/test/test_site_smoke.py`

**Interfaces:**
- Consumes: `lang_file(kind, lang)`、`site_data_dir(lang)`(Task 1)
- Produces: zh_cn 产物路径不变(`dist/data/…`、`dist/database.json`);非 zh_cn 输出 `dist/data/<code>/…`;新增 `dist/data/en/…`(官方原文,翻译为空);`--lang en` 内部使用 translations={}

- [ ] **Step 1: 写失败测试**

`scripts/test/test_site_smoke.py` 追加:
```python
def test_site_data_dir_drives_outputs(tmp_path, monkeypatch):
    import build
    official = json.loads((Path(__file__).parent / "fixtures" / "official.json").read_text(encoding="utf-8"))
    en_db, en_mods = build.build_all(official, {})          # en = 无翻译
    assert en_db["releases"][0]["description"].startswith("The mod loader")
```
（该测试证明"空翻译=官方原文"路径存在;目录写盘在 Step 3 冒烟覆盖。）

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest scripts/test/test_site_smoke.py -q`
Expected: 新增测试直接通过(锁定行为)或 FAIL(如 import 错误) — 两者皆可,红绿以 Step 4 冒烟为准。

- [ ] **Step 3: build.py main 多目录化**

将现有"读 translations/readmes/jams… + 写 data/"逻辑改造为对语言集合循环:
```python
    langs = ["zh_cn", "ja", "en"]            # en 为回退用的官方原文
    # zh_cn 额外写根 database.json 与根 data/(兼容现 URL)
    for lang in langs:
        translations = {}
        if lang != "en":
            translations = load_translations(lang_file("translations", lang)) \
                if lang_file("translations", lang).exists() else {}
        database_lang, mods_lang = build_all(official, translations)
        data_dir = Path(args.dist) / site_data_dir(lang)
        (data_dir / "releases").mkdir(parents=True, exist_ok=True)
        save_json(data_dir / "mods.json", {"mods": mods_lang, "meta": meta_with_lang(lang)})
        readmes = load_json(lang_file("readmes", lang)) if lang_file("readmes", lang).exists() else {}
        save_json(data_dir / "readmes.json", readmes)
        jams = load_json(lang_file("jams", lang)) if lang_file("jams", lang).exists() else {}
        save_json(data_dir / "jams.json", jams)
        jam_content = load_json(lang_file("jam_content", lang)) if lang_file("jam_content", lang).exists() else {}
        save_json(data_dir / "jam_content.json", jam_content)
        licenses = load_json(Path(args.licenses))
        save_json(data_dir / "licenses.json", licenses)
        patches = patches_payload(Path(args.patches), official)
        save_json(data_dir / "patches.json", patches)
        if lang == "zh_cn":
            save_json(dist / "database.json", database_lang)      # 保持 OWMM URL
    save_json(dist / "data" / "mods.json", ...)                   # zh_cn 根路径已由 data_dir==data 覆盖
```
（将原先每个文件的单次写替换为循环;`patches_payload` 把 Task(注册表)的解析/校验抽成小函数,原逻辑保留:解析失败打印并返回 `{}`。）
`meta_with_lang(lang)` 在 meta 里加 `"lang": lang`。

- [ ] **Step 4: 冒烟验证产物**

```bash
python scripts/build.py
ls dist/data dist/data/ja dist/data/en | head
python -c "import json; d=json.load(open('dist/data/en/mods.json')); print('en desc:', d['mods'][0]['description'][:30])"
```
Expected: 三个 data 目录存在;en 描述为官方英文原文;`dist/database.json` 仍为中文版。

- [ ] **Step 5: 提交**

```bash
git add scripts/build.py scripts/test/
git commit -m "feat: build 按语言目录输出(zh_cn 根路径不变;新增 ja/en 数据)"
```

---

### Task 3: 网站取数路由与回退链

**Files:**
- Modify: `site/js/i18n.js`(暴露 `window.LANG_DIR_CODE`;`zh-CN→zh_cn`,`ja→ja`)
- Modify: `site/js/app.js`(`withV` 改为 `contentUrl(name)`;统一 fetch 入口带回退)

**Interfaces:**
- `contentUrl(name) -> "data/x.json?v=…" | "data/ja/x.json?v=…"`(zh_cn → 根 data)
- `fetchContent(name)` 依回退链尝试;`mods.json` 缺失语言→zh_cn→en

- [ ] **Step 1: 写失败冒烟测试**

`scripts/test/test_site_smoke.py` 追加:
```python
def test_site_data_lang_routing_markers():
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    i18n = (REPO_ROOT / "site" / "js" / "i18n.js").read_text(encoding="utf-8")
    assert "contentUrl" in js and "fetchContent" in js
    assert "zh_cn" in i18n and "LANG_DIR_CODE" in i18n
```

- [ ] **Step 2: 运行确认失败**

Expected: FAIL(尚无标记)

- [ ] **Step 3: i18n.js 暴露目录代码**

`i18n.js` 中 `let lang` 赋值后追加:
```js
  const LANG_DIR = { "zh-CN": "zh_cn", ja: "ja" };
  window.LANG_DIR_CODE = LANG_DIR[lang] || "zh_cn";
```

- [ ] **Step 4: app.js 取数入口**

把 `withV(url)` 替换为:
```js
function contentUrl(name) {
  const base = (window.LANG_DIR_CODE === "zh_cn") ? "data/" : "data/" + window.LANG_DIR_CODE + "/";
  return base + name + "?v=" + (window.DATA_V || "");
}
```
保留 `fetchJson(url)`(接收完整 URL、解析 JSON、非 200 抛错),新增带回退的取数函数:
```js
// 先所选语言目录,404/缺失时回退官方英文(data/en/)——zh_cn 根目录即中文,无需第二跳
async function fetchContent(name) {
  const resp = await fetch(contentUrl(name));
  if (resp.ok) return resp.json();
  const respEn = await fetch("data/en/" + name + "?v=" + (window.DATA_V || ""));
  if (respEn.ok) return respEn.json();
  throw new Error("content 加载失败: " + name);
}
```
调用点统一改为相对名(去掉 `data/` 前缀),全部经 `fetchContent`:
- `loadMods()` → `fetchContent("mods.json")`
- `initReadme` → readmes / licenses(分别 `fetchContent("readmes.json")`、`fetchContent("licenses.json")`)
- `initReleases` → `fetchContent("releases/" + mod.uniqueName + ".json")`
- `initPatchBlock` → `fetchContent("patches.json")`
- `renderJams` → jams / jam_content(`fetchContent("jams.json")`、`fetchContent("jam_content.json")`)

- [ ] **Step 5: 验证**

```bash
node --check site/js/app.js && node --check site/js/i18n.js && python -m pytest scripts/test -q
python scripts/build.py && python -m http.server 0 &
```
浏览器抽查(本地):切换日本語后 mods 列表取 `data/ja/mods.json`(空则按回退显示 en 数据);中文仍正常。
(冒烟测试覆盖标记;交互验证列入手动清单。)

- [ ] **Step 6: 提交**

```bash
git add site/js/
git commit -m "feat: 网站内容按语言目录取数 + en 官方原文回退"
```

---

### Task 4: AI 目标语言参数化 + ja 试点

**Files:**
- Modify: `scripts/ai_client.py`(语言名参数)
- Modify: `scripts/translate.py`、`scripts/readmes.py`、`scripts/releases.py`(传目标语言)
- Create: `source/ja/{glossary,translations,readmes,releases_cache,human_translations,jams,jam_content}.json`(种子 `{}`/`[]`)

**Interfaces:**
- `translate_with_ai(..., target_lang: str = "简体中文")`;错误处理不变
- 脚本把 `--lang` 映射目标语言名:`LANG_NAME = {"zh_cn":"简体中文","ja":"日本語"}`
- ja glossary 首版种子:游戏日文官方译名(如 Nomai→ノマイ、量子の月→?),由人工取证后再填充;种子阶段允许空,仅跑通"结构+试点 N 条"

- [ ] **Step 1: 失败测试**

`scripts/test/test_ai_client.py` 追加:
```python
def test_target_lang_in_user_prompt(monkeypatch):
    fake = FakePost(httpx.Response(200, json={"choices": [{"message": {"content": "こんにちは"}}]}))
    monkeypatch.setattr(ai_client.httpx, "post", fake)
    ai_client.translate_with_ai("Hello", {}, base_url="u", api_key="k", model="m", target_lang="日本語")
    user = fake.calls[0][1]["messages"][1]["content"]
    assert "日本語" in user
```

- [ ] **Step 2: 运行确认失败**

Expected: FAIL — `unexpected keyword 'target_lang'`

- [ ] **Step 3: ai_client 参数化**

`translate_with_ai` 与 `translate_batch_with_ai` 增加 `target_lang: str = "简体中文"`,user prompt 文案:
```python
f"Translate the following text to {target_lang}.\nText:\n" + en_text
```
批量提示同步:`f"Translate each numbered text below to {target_lang}."`
(README/版本说明沿用同函数,自动继承。)

- [ ] **Step 4: 脚本传参**

三个脚本各加模块常量与透传:
```python
LANG_NAME = {"zh_cn": "简体中文", "ja": "日本語"}

def ai_translate(text):
    return ai_client.translate_with_ai(text, glossary,
        base_url=..., api_key=..., model=...,
        target_lang=LANG_NAME.get(lang, "简体中文"))
```
在各自 main 的 ai 闭包处接入;批量函数同理。

- [ ] **Step 5: ja 种子与试点**

```bash
mkdir -p source/ja
for f in glossary translations readmes releases_cache human_translations; do echo '{}' > source/ja/$f.json; done
echo '[]' > source/ja/readme_denylist.json 2>/dev/null || true
printf '{\n "overrides": {},\n "fallbackTitle": "その他のJam作品"\n}\n' > source/ja/jams.json
echo '{"index": [], "pages": {}}' > source/ja/jam_content.json
python -m pytest scripts/test -q
```
Expected: 全绿

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "feat: AI 目标语言参数化(zh_cn/ja);ja 目录种子与试点通路"
```

---

### Task 5: CI 与文档

**Files:**
- Modify: `.github/workflows/sync-translate.yml`
- Modify: `README.md`、`source/README.md`

- [ ] **Step 1: workflow 增加 lang 输入**

```yaml
      lang:
        description: '语言目录代码(zh_cn=默认;ja 等增量)'
        type: string
        default: 'zh_cn'
```
各 python 步骤命令追加 `--lang ${{ inputs.lang }}`;build 恒为 `--lang zh_cn`(zh 库保持),ja 站点数据在 build 循环内统一产出(需 ja 数据已同步;由同 job 顺序保证)。

- [ ] **Step 2: 文档更新**

README「工作方式/维护」与 `source/README.md`:
- 语言化文件路径示例改 `source/zh_cn/…`、`source/ja/…`
- 新增一节「多语言」:目录代码与显示语言映射、如何新增语言(加目录+词典+映射表)、ja 术语取证要求
- 本地命令示例带 `--lang ja`(可选)

- [ ] **Step 3: 全量回归**

```bash
python -m pytest scripts/test -q
git status --short
```
Expected: 全绿、工作区干净

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "chore: CI lang 输入与多语言文档"
```

---

## 手动验收清单(实施后)

1. 线上中文站与 database.json 行为与迁移前一致(URL 不变、内容不变)
2. `dist/data/en/mods.json` 为官方英文原文(回退用)
3. 切换日本語:界面文案日化;ja 数据目录存在、空内容回退 en 不空白
4. 用 `--lang ja --limit 20` 试点翻译后,日语简介出现在 `data/ja/mods.json`
