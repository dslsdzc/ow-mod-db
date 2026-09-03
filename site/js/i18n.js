/* 多语言界面框架 (默认 zh-CN; 新增语言 = 在 I18N 加一份词典)
 * 用法:
 *   1) 静态文案: 元素加 data-i18n="key" (只替换纯文本)
 *   2) JS 文案:   window.t('key') 或 t('key', {n: 5}) 占位 {n}
 * 切换: 自动注入语言下拉(右上导航),偏好存 localStorage('ui-lang')
 */
window.I18N = {
  "zh-CN": {
    "brand": "星际拓荒 MOD",
    "nav.mods": "全部 MOD",
    "nav.jams": "历届 Jam",
    "nav.manager": "Mod Manager",
    "home.popular": "热门 MOD",
    "home.popularNew": "热门新 MOD",
    "home.updated": "最近更新",
    "home.communityTitle": "交流与反馈",
    "home.communityDesc": "发现翻译错误、想推荐更好的译名、或讨论某个 MOD?来这些地方:",
    "home.communityDiscuss": "GitHub 讨论区",
    "home.communityIssue": "提交翻译问题",
    "home.communityOfficial": "官方 MOD 站",
    "home.contributeTitle": "成为汉化贡献者",
    "home.contributeDesc": "本站由 AI 自动汉化起步,长期目标是由人工精校逐步接管。你可以直接给术语表或人工翻译库提 PR——推送后几分钟内自动生效,机器翻译永不会覆盖人工译文。",
    "home.contributeGuide": "查看维护指南",
    "home.contributeBrowse": "浏览术语表与人工翻译",
    "mods.title": "全部 MOD",
    "mods.search": "搜索 MOD 名称 / 简介…",
    "mods.sort.installs": "按热门排序",
    "mods.sort.newest": "按最新发布",
    "mods.sort.updated": "按最近更新",
    "mods.sort.name": "按名称",
    "mods.allTag": "全部",
    "mods.count": "{n} / {m} 个 MOD",
    "mods.none": "没有匹配的 MOD",
    "meta.downloads": "{n} 次下载",
    "meta.updatedAt": "更新于 {d}",
    "jams.title": "历届 Game Jam",
    "jams.works": "{n} 个作品",
    "jams.placeholder": "暂未识别到 Jam 参赛 mod",
    "manager.title": "Outer Wilds Mod Manager(OWMM)",
    "backTop": "回到顶部"
  },
  "ja": {
    "brand": "アウターワイルズ MOD",
    "nav.mods": "すべてのMOD",
    "nav.jams": "過去のJam",
    "nav.manager": "Mod Manager",
    "home.popular": "人気MOD",
    "home.popularNew": "注目の新着MOD",
    "home.updated": "最近の更新",
    "home.communityTitle": "交流・フィードバック",
    "home.communityDesc": "誤訳を見つけた、より良い訳語を提案したい、MODについて話したい——こちらへ:",
    "home.communityDiscuss": "GitHub ディスカッション",
    "home.communityIssue": "翻訳の問題を報告",
    "home.communityOfficial": "公式MODサイト",
    "home.contributeTitle": "翻訳コントリビューターになる",
    "home.contributeDesc": "本サイトはAI翻訳から始まり、長期的には人間による校訂へ引き継ぎます。用語集や手動翻訳リポジトリへのPRは数分で自動反映され、機械翻訳が手動訳を上書きすることはありません。",
    "home.contributeGuide": "メンテナンスガイド",
    "home.contributeBrowse": "用語集と手動翻訳を閲覧",
    "mods.title": "すべてのMOD",
    "mods.search": "MOD名・説明文を検索…",
    "mods.sort.installs": "人気順",
    "mods.sort.newest": "新しい順",
    "mods.sort.updated": "更新順",
    "mods.sort.name": "名前順",
    "mods.allTag": "すべて",
    "mods.count": "{n} / {m} 個のMOD",
    "mods.none": "該当するMODがありません",
    "meta.downloads": "{n} 回DL",
    "meta.updatedAt": "更新 {d}",
    "jams.title": "歴代 Game Jam",
    "jams.works": "{n} 作品",
    "jams.placeholder": "Jam参加MODを認識できませんでした",
    "manager.title": "Outer Wilds Mod Manager(OWMM)",
    "backTop": "ページ上部へ"
  }
};

(function initI18n() {
  const DICT = window.I18N || {};
  const LANG_KEY = "ui-lang";
  const FALLBACK = "zh-CN";
  let lang = FALLBACK;
  try { lang = localStorage.getItem(LANG_KEY) || FALLBACK; } catch (e) { /* ignore */ }
  if (!DICT[lang]) lang = FALLBACK;

  window.t = function t(key, params) {
    const table = DICT[lang] || DICT[FALLBACK] || {};
    let s = table[key] !== undefined ? table[key] : ((DICT[FALLBACK] || {})[key] !== undefined ? DICT[FALLBACK][key] : key);
    if (params) {
      for (const k of Object.keys(params)) s = String(s).replaceAll("{" + k + "}", String(params[k]));
    }
    return s;
  };

  document.documentElement.lang = lang === "zh-CN" ? "zh-CN" : lang;

  function apply() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const v = window.t(el.dataset.i18n);
      if (v) el.textContent = v;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const v = window.t(el.dataset.i18nPlaceholder);
      if (v) el.setAttribute("placeholder", v);
    });
  }

  function addLangSwitcher() {
    const nav = document.querySelector(".site-header nav");
    if (!nav || document.getElementById("lang-switch")) return;
    const sel = document.createElement("select");
    sel.id = "lang-switch";
    sel.className = "lang-switch";
    sel.setAttribute("aria-label", "Language / 語言");
    sel.innerHTML = '<option value="zh-CN">中文</option><option value="ja">日本語</option>';
    sel.value = lang;
    sel.addEventListener("change", () => {
      try { localStorage.setItem(LANG_KEY, sel.value); } catch (e) { /* ignore */ }
      location.reload();
    });
    nav.appendChild(sel);
  }

  document.addEventListener("DOMContentLoaded", () => {
    apply();
    addLangSwitcher();
  });
})();
