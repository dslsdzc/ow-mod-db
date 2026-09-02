from patch_registry import patches_to_dict, validate_patches

OFFICIAL = {"Alek.OWML", "Hawkbar.GhostInTheMachine", "SBtT.TheOutsider",
            "xxx.GhostInTheMachineCN"}


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
    assert errs == ["告警: target Hawkbar.GhostInTheMachine 重复登记 2 次,以最后一条为准"]


def test_scalar_or_none_entries_do_not_crash():
    assert validate_patches([None, "string", 3, {"patch": {}}], OFFICIAL)
    assert any("不是对象" in e for e in validate_patches(["x"], OFFICIAL))


def test_patch_non_dict_reports():
    errs = validate_patches([{"target": "Hawkbar.GhostInTheMachine", "patch": "oops"}], OFFICIAL)
    assert any("patch 不是对象" in e for e in errs)


def test_patches_to_dict_later_wins():
    a = _patch()
    b = _patch(patch={"uniqueName": "yyy.CN", "name": "新版", "install": "owmm",
                      "url": "", "note": "", "addedAt": ""})
    d = patches_to_dict([a, b])
    assert d["Hawkbar.GhostInTheMachine"]["uniqueName"] == "yyy.CN"
    assert len(d) == 1
