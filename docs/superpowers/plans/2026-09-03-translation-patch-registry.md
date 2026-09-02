# 中文汉化补丁注册表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立人工维护的补丁注册表并在 MOD 详情页提供"中文汉化补丁"一键安装/下载入口。

**Architecture:** 三个小单元: ① `scripts/patch_registry.py` 纯函数校验注册表(依赖官方库快照); ② `scripts/build.py` 把注册表数组复制为 `dist/data/patches.json` 字典; ③ `site/js/app.js` 详情页按 target 查注册表渲染安装块(owmm 深链或 manual 直链)。注册表条目人工编辑 `source/translation_patches.json`,推送即自动部署。

**Tech Stack:** Python 3.11 + pytest;原生 HTML/JS(沿用现有 site 模式);GitHub Actions 既有流水线。

## Global Constraints

- 注册表文件 `source/translation_patches.json`,初始为 `[]`(机制先行,条目后填)
- 字段规则(校验失败必须报错并列出): `target` 存在且非空;`patch` 存在;`patch.install` ∈ {"owmm","manual"};install=owmm 时 `patch.uniqueName` 必填且存在于官方快照 releases 的 uniqueName 集合;install=manual 时 `patch.url` 必填且以 http 开头;重复 `target` 产生告警(不阻塞)
- 构建产物 `dist/data/patches.json` 为字典 `{target: patch}`;注册表为空时产物为 `{}`
- 页面: 详情页「中文汉化补丁」块位于按钮区之后;无条目零渲染;注明"补丁为社区作品,版权归作者"
- 测试从仓库根目录执行 `python -m pytest scripts/test -q`

---

### Task 1: 注册表种子与校验模块

**Files:**
- Create: `source/translation_patches.json`
- Create: `scripts/patch_registry.py`
- Create: `scripts/test/test_patch_registry.py`

**Interfaces:**
- Produces:
  - `validate_patches(patches: list, official_ids: set) -> list[str]` — 返回错误消息列表(空列表 = 通过)
  - `patches_to_dict(patches: list) -> dict` — `[{target, patch}]` → `{target: patch}`;重复 target 后者覆盖
- 后续任务依赖上述两个签名。

- [ ] **Step 1: 建种子文件**

`source/translation_patches.json`:
```json
[]
```

- [ ] **Step 2: 写失败测试**

`scripts/test/test_patch_registry.py`:
```python
import pytest

from patch_registry import patches_to_dict, validate_patches

OFFICIAL = {"Alek.OWML", "Hawkbar.GhostInTheMachine", "SBtT.TheOutsider"}


def _patch(install="owmm", **over):
    base = {
        "target": "Hawkbar.GhostInTheMachine",
        "patch": {"uniqueName": "xxx.GhostInTheMachineCN", "name": "中文补丁",
                  "install": install, "url": "", "note": "n", "addedAt": "2026-09-03"},
    }
    if over:
        base.update(over)
    return base


def test_empty_list_valid():
    assert validate_patches([], OFFICIAL) == []


def test_valid_owmm_entry():
    assert validate_patches([_patch()], OFFICIAL) == []


def test_missing_target_fails():
    errs = validate_patches([_patch(target="No.SuchMod")], OFFICIAL)
    assert any("No.SuchMod" in e and "target" in e for e in errs)


def test_owmm_patch_must_exist_in_official():
    errs = validate_patches([_patch(patch={"uniqueName": "Ghost.Unknown", "name": "x",
                                           "install": "owmm", "url": "", "note": "",
                                           "addedAt": ""})], OFFICIAL)
    assert any("Ghost.Unknown" in e for e in errs)


def test_manual_requires_url():
    errs = validate_patches([_patch(install="manual",
                                    patch={"uniqueName": "", "name": "x", "install": "manual",
                                           "url": "", "note": "", "addedAt": ""})], OFFICIAL)
    assert any("url" in e for e in errs)


def test_unknown_install_mode_fails():
    errs = validate_patches([_patch(install="steam")], OFFICIAL)
    assert any("install" in e for e in errs)


def test_duplicate_target_warns_but_passes():
    errs = validate_patches([_patch(), _patch()], OFFICIAL)
    assert any("重复" in e for e in errs)          # 告警存在
    assert not any("must" in e for e in errs)       # 无阻塞错误


def test_patches_to_dict_later_wins():
    a = _patch()
    b = _patch(patch={"uniqueName": "yyy.CN", "name": "新版", "install": "owmm",
                      "url": "", "note": "", "addedAt": ""})
    d = patches_to_dict([a, b])
    assert d["Hawkbar.GhostInTheMachine"]["uniqueName"] == "yyy.CN"
    assert len(d) == 1
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest scripts/test/test_patch_registry.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'patch_registry'`

- [ ] **Step 4: 实现 patch_registry.py**

`scripts/patch_registry.py`:
```python
"""中文汉化补丁注册表校验与转换(纯函数,无 I/O)."""

INSTALL_MODES = {"owmm", "manual"}


def validate_patches(patches: list, official_ids: set) -> list[str]:
    """校验注册表;返回错误/告警消息列表(空 = 通过)."""
    errors: list[str] = []
    seen: dict[str, int] = {}
    for i, entry in enumerate(patches):
        idx = f"条目 {i}"
        target = (entry or {}).get("target")
        patch = (entry or {}).get("patch") or {}
        if not target:
            errors.append(f"{idx}: 缺少 target")
            continue
        seen[target] = seen.get(target, 0) + 1
        if target not in official_ids:
            errors.append(f"{idx}: target {target} 不在官方库中")
        install = patch.get("install")
        if install not in INSTALL_MODES:
            errors.append(f"{idx}: {target} patch.install 必须是 owmm 或 manual(实际: {install!r})")
            continue
        if install == "owmm":
            un = patch.get("uniqueName")
            if not un:
                errors.append(f"{idx}: {target} install=owmm 时 patch.uniqueName 必填")
            elif un not in official_ids:
                errors.append(f"{idx}: 补丁 {un} 不在官方库中,无法 owmm 深链")
        else:  # manual
            url = patch.get("url")
            if not url or not str(url).startswith("http"):
                errors.append(f"{idx}: {target} install=manual 时 patch.url 必填且以 http 开头")
    for target, count in seen.items():
        if count > 1:
            errors.append(f"告警: target {target} 重复登记 {count} 次,以最后一条为准")
    return errors


def patches_to_dict(patches: list) -> dict:
    """[{target, patch}] -> {target: patch};重复 target 后者覆盖."""
    out: dict[str, dict] = {}
    for entry in patches:
        target = (entry or {}).get("target")
        patch = (entry or {}).get("patch")
        if target and isinstance(patch, dict):
            out[target] = patch
    return out
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest scripts/test/test_patch_registry.py -q`
Expected: 8 passed

- [ ] **Step 6: 提交**

```bash
git add source/translation_patches.json scripts/patch_registry.py scripts/test/test_patch_registry.py
git commit -m "feat: 补丁注册表种子与校验模块"
```

---

### Task 2: 构建产物 patches.json

**Files:**
- Modify: `scripts/build.py`
- Modify: `scripts/test/test_site_smoke.py`

**Interfaces:**
- Consumes: `patches_to_dict(patches) -> dict`(Task 1)
- Produces: `dist/data/patches.json`(字典或 `{}`);`build.py` 新增 `--patches` 参数,默认 `source/translation_patches.json`

- [ ] **Step 1: 写失败测试(扩展冒烟测试)**

`scripts/test/test_site_smoke.py` 中新增 import 与测试(文件顶部现为 `import json` / `from pathlib import Path`,保持):

```python
from patch_registry import patches_to_dict, validate_patches


def test_patches_payload_shape():
    patches = [
        {"target": "Hawkbar.GhostInTheMachine",
         "patch": {"uniqueName": "yyy.CN", "name": "补丁", "install": "owmm",
                   "url": "", "note": "", "addedAt": ""}},
    ]
    assert validate_patches(patches, {"Hawkbar.GhostInTheMachine", "yyy.CN"}) == []
    payload = patches_to_dict(patches)
    assert payload == {"Hawkbar.GhostInTheMachine": payload["Hawkbar.GhostInTheMachine"]}
    assert payload["Hawkbar.GhostInTheMachine"]["uniqueName"] == "yyy.CN"
    assert patches_to_dict([]) == {}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest scripts/test/test_site_smoke.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'patch_registry'`(Task 1 未先执行时;若按顺序执行则应已存在,此测试用于锁定形状)

- [ ] **Step 3: 修改 build.py**

`scripts/build.py` 的 `main()`:
1. 参数区新增(在 `--releases` 之后):
```python
    parser.add_argument("--patches", default="source/translation_patches.json",
                        help="中文汉化补丁注册表")
```
2. 在"版本历史"复制块(写 `rel_dir/...` 的 for 循环)之后新增:
```python
    # 中文汉化补丁注册表(target -> patch;空表为 {});校验只打印,不阻塞构建
    import json as _json
    from patch_registry import patches_to_dict, validate_patches
    _patch_path = Path(args.patches)
    if _patch_path.exists():
        patches = _json.loads(_patch_path.read_text(encoding="utf-8"))
        _ids = {m.get("uniqueName", "") for m in official.get("releases", [])}
        for _e in validate_patches(patches, _ids):
            print(f"  注册表校验: {_e}")
    else:
        patches = []
    save_json(dist / "data" / "patches.json", patches_to_dict(patches))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest scripts/test -q`
Expected: 全绿(原 76 + 新增 1)

- [ ] **Step 5: 本地冒烟(空表产物)**

Run: `python scripts/build.py`
Expected: 输出含 `已生成`;随后:
`python -c "import json; d=json.load(open('dist/data/patches.json')); print(d)"`
Expected: `{}`

- [ ] **Step 6: 提交**

```bash
git add scripts/build.py scripts/test/test_site_smoke.py
git commit -m "feat: 构建产物包含补丁注册表 data/patches.json"
```

---

### Task 3: 详情页中文补丁块

**Files:**
- Modify: `site/js/app.js`
- Modify: `scripts/test/test_site_smoke.py`(页面标记断言)

**Interfaces:**
- Consumes: `dist/data/patches.json`(Task 2 产物,`{target: {uniqueName,name,install,url,note,addedAt}}`)
- Produces: 详情页函数 `initPatchBlock(mod)`,在 `renderDetail` 末尾调用(位于 `initComments(mod)` 之前)

- [ ] **Step 1: 写失败冒烟测试(标记)**

`scripts/test/test_site_smoke.py` 的 `test_mirror_pages_cover_three_views` 之后新增:

```python
def test_patch_block_markers_present():
    js = (REPO_ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    assert "patches.json" in js
    assert "initPatchBlock" in js
    assert "owmods://install-mod/" in js
    assert "中文汉化补丁" in js
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest scripts/test/test_site_smoke.py::test_patch_block_markers_present -q`
Expected: FAIL(js 尚无这些标记)

- [ ] **Step 3: 实现 initPatchBlock 并接线**

`site/js/app.js`:

1) 在 `renderDetail` 的 `</div>`(detail 容器结束)之前、`addons-section` 之后插入占位块:
```js
      <div class="section" id="patch-section" hidden>
        <h3>中文汉化补丁</h3>
        <div id="patch-box"></div>
      </div>
```
(紧跟在 `releases-section` 块之后。)

2) 在 `initReleases` 函数之前新增:

```js
function initPatchBlock(mod) {
  const section = document.getElementById("patch-section");
  const box = document.getElementById("patch-box");
  if (!section || !box) return;
  fetchJson("data/patches.json")
    .then((patches) => {
      const p = patches[mod.uniqueName];
      if (!p) { section.remove(); return; }
      section.hidden = false;
      const installBtn = p.install === "owmm" && p.uniqueName
        ? `<a class="cta" href="owmods://install-mod/${encodeURIComponent(p.uniqueName)}"
             title="需已安装 Outer Wilds Mod Manager">一键安装补丁</a>`
        : (p.url ? `<a class="cta" href="${esc(p.url)}" target="_blank" rel="noopener">下载补丁</a>` : "");
      const manualNote = p.install === "manual"
        ? `<p class="foot-note">下载后放入 Mods 文件夹,或用 OWMM 安装 zip。</p>` : "";
      box.innerHTML =
        `<div><p style="margin:0 0 .4rem;">${esc(p.name || "中文汉化补丁")}</p>
         <div class="cta-row">${installBtn}</div>
         ${p.note ? `<p class="foot-note">${esc(p.note)}</p>` : ""}
         ${manualNote}
         <p class="foot-note">补丁为社区作品,版权归作者所有。</p></div>`;
    })
    .catch(() => section.remove());
}
```

3) `renderDetail` 末尾调用(在 `initReleases(mod);` 之后、`initComments(mod);` 之前):
```js
  initPatchBlock(mod);
```

- [ ] **Step 4: 运行测试确认通过**

Run: `node --check site/js/app.js && python -m pytest scripts/test -q`
Expected: JS OK;全绿

- [ ] **Step 5: 本地渲染验证(假数据)**

Run:
```bash
python - <<'EOF'
import json
official = json.load(open('source/official.json'))
ids = {m['uniqueName'] for m in official['releases']}
fake = [{"target": "Hawkbar.GhostInTheMachine",
         "patch": {"uniqueName": "yyy.CN", "name": "测试补丁", "install": "owmm",
                   "url": "", "note": "本地验证用", "addedAt": "2026-09-03"}}]
# 补丁需在官方库才过校验;此处仅验证 UI 形状,故用手动模式直链
fake[0]["patch"] = {"uniqueName": "", "name": "测试补丁(手动)", "install": "manual",
                    "url": "https://example.com/patch.zip", "note": "本地验证", "addedAt": "2026-09-03"}
json.dump({"mods": json.load(open('dist/data/mods.json'))["mods"],
           "meta": {}}, open('/tmp/fake_mods.json', 'w'), ensure_ascii=False)
json.dump({"Hawkbar.GhostInTheMachine": fake[0]["patch"]}, open('/tmp/fake_patches.json', 'w'), ensure_ascii=False)
print("假数据已生成,手工把 dist/data/ 下对应文件替换后本地预览即可(见 README 本地运行)")
EOF
```
(注: 真实验证以线上空注册表零渲染 + 后续真实条目登记后的部署验收为准;此步确保页面逻辑无语法错误即可。)

- [ ] **Step 6: 提交**

```bash
git add site/js/app.js scripts/test/test_site_smoke.py
git commit -m "feat: 详情页中文汉化补丁块(owmm 一键安装/manual 下载,无条目零渲染)"
```
