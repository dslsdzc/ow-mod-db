# RFC: Standard association between story mods and their localization patches

> 草稿,供用户决定是否与措辞后发到 ow-mods/ow-mod-man 或 ow-mods/ow-mod-db 的 issues。

---

**Title:** [Feature Request] Standard way to associate a localization patch with the mod it translates

**Body:**

## Problem

Localization patches exist for many story mods (e.g. a community Simplified-Chinese patch for *Ghost in the Machine*, a Chinese translation file for *The Outsider*). Today there is **no standard field** that says "this mod is a translation patch for mod X":

- Translators publish patches as separate OWML mods (often depending on `xen.LocalizationUtility`), but discovery is manual ("search the patch's name").
- Players must already know a patch exists and what it is called to find it.
- Websites/managers cannot surface "translations available for this mod" without a convention.

This affects every language community (Chinese, Korean, Japanese, Russian…), not just one.

## Proposal

1. **Manifest/DB field**: allow a mod to declare which mod(s) it localizes, e.g. `"translationOf": ["<target uniqueName>"]` (or reuse/extend the existing `parent` semantics with an explicit meaning).
2. **Database**: `ow-mod-db` accepts the field and exposes it in `database.json`.
3. **OWMM UI**: on a mod's page, if patches with matching `translationOf` exist, show "中文/한국어/… translation available" and install them like any mod.
4. **Website**: same association shown on `outerwildsmods.com`.

## Minimal implementation sketch

- Schema: optional array field in the mod manifest → copied into `database.json` entries.
- Matching: `translationOf == target.uniqueName`, symmetrical to how `parent` is displayed today.
- No installer changes needed (patches remain ordinary mods).

## Open questions

- Field name: `translationOf` vs `translates` vs reusing `parent`?
- Should a patch be allowed to declare multiple targets?
- Should OWMM auto-enable dependencies (`xen.LocalizationUtility`) when enabling the patch?

## Context

We run a Simplified-Chinese mirror of the mod database (github.com/dslsdzc/ow-mod-db). While waiting for a standard, we maintain a small curated registry of community patches and offer one-click install from each mod's detail page. We'd be happy to migrate to an upstream standard and to help test.
