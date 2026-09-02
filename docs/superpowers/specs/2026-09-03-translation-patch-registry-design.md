# 中文汉化补丁注册表 + 一键安装入口 设计

日期: 2026-09-03
状态: 已获用户批准(机制先行,条目后填)

## 背景与目标

部分剧情 MOD(如《机器中的幽灵》)本体无中文,社区存在中文汉化补丁,但缺少"哪个 MOD 有补丁、补丁在哪、怎么装"的标准入口。官方库(413 个条目)中目前**没有任何剧情 MOD 的中文补丁条目**,社区补丁分布零散(贴吧/B站/QQ 群/独立分发)。

**本阶段目标**: 建立"补丁注册表"机制 + 详情页一键安装入口,条目由人工登记、推送即生效。官方库条目出现后优先走 `owmods://` 深链,否则提供手动下载。

**明确不做**: 不改 OWMM、不开上游 issue、不自动发现补丁。上游标准格式推进由用户另行决定。

## 数据层

新增人工维护文件 `source/translation_patches.json`(数组):

```json
[
  {
    "target": "Hawkbar.GhostInTheMachine",
    "patch": {
      "uniqueName": "xxx.GhostInTheMachineCN",
      "name": "机器中的幽灵 中文补丁",
      "install": "owmm",
      "url": "",
      "note": "社区精翻 v1.2(出处链接)",
      "addedAt": "2026-09-03"
    }
  }
]
```

字段规则:
- `target`: 目标 MOD 的 uniqueName,必须存在于官方库快照 `source/official.json`
- `patch.install`: `"owmm"`(补丁在官方库,可深链安装)或 `"manual"`(提供 zip 直链 + 手动说明)
- `patch.uniqueName`: install=owmm 时必填,且必须存在于官方库快照
- `patch.url`: install=manual 时必填(zip 直链)
- `patch.note`: 补丁作者/版本/出处(展示用,可空)
- `addedAt`: 登记日期(ISO,可空)
- 重复 `target` 以最后一条为准(校验时告警)

构建时复制为 `dist/data/patches.json`(字典: target → patch),随站部署。

## 页面

详情页新块「中文汉化补丁」(位于按钮区之后):
- 补丁名 + note(注明"补丁为社区作品,版权归作者")
- install=owmm → 「一键安装」按钮(`owmods://install-mod/<patch.uniqueName>`)
- install=manual → 「下载补丁」链接(`patch.url`)+ 一行说明:"下载后放入 Mods 文件夹,或用 OWMM 安装 zip"
- 该 MOD 无注册条目时整块不渲染(零干扰)

## 校验与测试

- 登记校验(纯函数 + 单测): schema 字段;target 存在;install=owmm 时 patch.uniqueName 存在于官方快照;重复 target 告警
- 构建复制测试: dist/data/patches.json 存在且形状正确(空表时为 `{}`)
- 页面渲染: 空表零渲染;构造假 patches.json 本地验证按钮/两种 install 分支

## 流程

登记 = 编辑 JSON → 推送 → CI 自动部署 → 玩家详情页见入口。条目由用户/汉化团队从社区发布处收集核实后登记。
