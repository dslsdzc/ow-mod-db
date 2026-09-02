"""中文汉化补丁注册表校验与转换(纯函数,无 I/O)."""

INSTALL_MODES = {"owmm", "manual"}


def validate_patches(patches: list, official_ids: set) -> list[str]:
    """校验注册表;返回错误/告警消息列表(空 = 通过)."""
    errors: list[str] = []
    seen: dict[str, int] = {}
    for i, entry in enumerate(patches):
        idx = f"条目 {i}"
        if not isinstance(entry, dict):
            errors.append(f"{idx}: 条目不是对象({type(entry).__name__})")
            continue
        target = entry.get("target")
        patch = entry.get("patch") or {}
        if not isinstance(patch, dict):
            errors.append(f"{idx}: target {target} 的 patch 不是对象")
            continue
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
