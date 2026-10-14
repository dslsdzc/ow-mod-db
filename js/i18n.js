/* 多语言界面框架 (默认 zh-CN; 新增语言 = 在 I18N 加一份词典)
 * 用法:
 *   1) 静态文案: 元素加 data-i18n="key" (只替换纯文本)
 *   2) JS 文案:   window.t('key') 或 t('key', {n: 5}) 占位 {n}
 *   3) 属性文案: data-i18n-placeholder / data-i18n-aria-label / data-i18n-title
 * 切换: 自动注入语言下拉(右上导航),偏好存 localStorage('ui-lang')
 */
window.I18N = {
  "zh-CN": {
    "site.name": "星际拓荒 MOD 数据库",
    "brand": "星际拓荒 MOD",
    "a11y.skip": "跳到主要内容",
    "a11y.nav": "主导航",
    "nav.mods": "全部 MOD",
    "nav.jams": "历届 Jam",
    "nav.manager": "Mod Manager",
    "home.title": "星际拓荒 MOD",
    "home.intro1": "是《星际拓荒》的非官方修改,可添加新功能、改进与额外内容。使用",
    "home.intro2": "即可轻松下载安装。",
    "home.total": "目前共有 {n} 个 MOD、扩展与工具。",
    "home.syncInfo": "数据同步于 {t} UTC · {done}/{total} 个简介已汉化",
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
    "footer.legal1": "非官方翻译镜像站 · 数据来自",
    "footer.legal2": "· 数据库 (MIT) © ow-mods · MOD 元数据版权归各自作者 · AI 自动汉化,人工精校持续更新",
    "footer.mirror": "非官方翻译镜像站",
    "footer.home": "首页",
    "footer.dbHint1": "在 Mod Manager 中把数据库网址设为",
    "footer.dbUrl": "https://dslsdzc.github.io/ow-mod-db/database.json",
    "footer.dbHint2": "即可在游戏内使用中文简介",
    "footer.repo": "GitHub 仓库",
    "footer.tagline": "简介自动翻译 · 更新于",
    "mods.title": "全部 MOD",
    "mods.search": "搜索 MOD 名称 / 简介…（支持英文原名）",
    "mods.searchLabel": "搜索 MOD",
    "mods.sortLabel": "排序方式",
    "mods.sort.installs": "按热门排序",
    "mods.sort.newest": "按最新发布",
    "mods.sort.updated": "按最近更新",
    "mods.sort.name": "按名称",
    "mods.allTag": "全部",
    "mods.count": "{n} / {m} 个 MOD",
    "mods.none": "没有匹配的 MOD",
    "meta.downloads": "{n} 次下载",
    "meta.updatedAt": "更新于 {d}",
    "detail.notFound": "未找到该 MOD，",
    "detail.notFoundTitle": "未找到",
    "detail.backList": "返回列表",
    "detail.desc": "简介",
    "detail.latestRelease": "最新版本更新说明",
    "detail.addons": "附属与变体",
    "detail.releaseHistory": "版本历史",
    "detail.patchSection": "中文支持",
    "detail.comments": "讨论区",
    "detail.commentsHint": "评论由 GitHub Discussions 驱动 · 英文评论可用浏览器自带翻译阅读",
    "detail.downloadZip": "下载 zip",
    "detail.repoLink": "源代码仓库",
    "detail.install": "一键安装",
    "detail.installHint": "需要已安装 Outer Wilds Mod Manager",
    "detail.reportIssue": "报告翻译问题",
    "detail.share": "分享",
    "detail.copied": "已复制链接",
    "trend.title": "下载趋势",
    "trend.loading": "加载趋势中…",
    "trend.failed": "趋势数据暂时无法获取",
    "trend.noData": "该 MOD 暂无趋势数据（新上传的 MOD 统计积累中）",
    "trend.viewOnOfficial": "在官方站查看",
    "trend.source": "数据来自 outerwildsmods.com",
    "readme.libMissing": "渲染库未加载(CDN 不可达),",
    "readme.openRepo": "打开仓库原文目录",
    "readme.aiNote": "译文由 AI 生成 · 原文版权归作者所有\u00a0·\u00a0{lic}",
    "readme.backTranslation": "回到中文译文",
    "readme.viewOriginal": "查看英文原文",
    "readme.originalNote": "英文原文 · 原文版权归作者所有",
    "readme.msView": "翻译",
    "readme.msLoading": "翻译中…",
    "readme.msFailed": "翻译失败",
    "readme.msResult": "即时翻译结果 · {base}",
    "readme.msFailedMsg": "翻译失败:{msg}（可换用浏览器自带翻译）",
    "readme.msHint": "{lic} 许可 · 译文生成中，可用「翻译」即时浏览（不保存）",
    "readme.msOnlyOnce": "仅本次查看，不保存",
    "readme.msCopyright": "原文版权归作者所有 · 仅本次阅读，不保存",
    "readme.licenseNone": "未声明(保留所有权利)",
    "readme.noLicenseHint": "仓库许可为 {lic}，未保存译文；下方按钮为即时翻译，仅供本次阅读、不保存",
    "readme.fetchFailed": "README 加载失败:",
    "readme.loadFailed": "加载失败:",
    "patch.install": "一键安装补丁",
    "patch.download": "下载补丁",
    "patch.hint": "下载后放入 Mods 文件夹，或用 OWMM 安装 zip。",
    "patch.note": "补丁为社区作品，版权归作者所有。",
    "releases.original": "原文",
    "releases.translation": "中文译文",
    "releases.translateAll": "全部翻译",
    "releases.showAll": "显示全部 {n} 个版本",
    "jams.title": "历届 Game Jam",
    "jams.works": "{n} 个作品",
    "jams.placeholder": "暂未识别到 Jam 参赛 mod",
    "jams.fallbackTitle": "其他 Jam 作品",
    "jams.missingTitle": "历届 Jam 届次（待补充）",
    "jams.intro": "星际拓荒社区定期举办模组制作 Jam。这里按届自动聚合参赛 MOD（按官方库标签与命名识别），排序按热门度；届次的中文规则与说明见各分组。",
    "jams.groupNote": "译文依据官方 Jam 页面撰写，版权归主办方；参赛作品列表为本站自动聚合。",
    "jams.officialLink": "官方届次页面",
    "jams.officialPage": "官方 Jam 页面",
    "jams.toOfficial": "前往官方页面",
    "jams.renderFailed": "Jam 页渲染失败:",
    "notfound.msg": "页面不存在（404）……也许是量子态把它藏起来了。",
    "notfound.home": "回到首页",
    "notfound.browse": "浏览全部 MOD",
    "manager.title": "Outer Wilds Mod Manager(OWMM)",
    "manager.intro": "官方出品的 MOD 管理器:一键下载、安装、更新 MOD,管理游戏内翻译,加载 OWML 模组框架。本站(中文镜像)的数据可以直接在管理器里使用。",
    "manager.dlTitle": "下载与安装",
    "manager.dlStep1": "1. 到官方发布页下载最新版(Windows 便携版或安装版),解压后运行即可。",
    "manager.dlStep2": "2. 管理器会自动安装 OWML 框架;首次运行按提示选择游戏安装目录。",
    "manager.dlLink": "官方下载页面",
    "manager.officialPage": "官网介绍页",
    "manager.useTitle": "使用本站中文数据库",
    "manager.useStep1": "在 Mod Manager 中打开 设置(齿轮) → Advanced / 高级,把 Database URL 改为本站地址,游戏内就会显示中文简介:",
    "manager.useNote": "之后每次启动管理器都会自动检查本站最新数据(约 30 分钟轮询同步上游,新增 MOD 自动翻译)。",
    "manager.noteTitle": "说明",
    "manager.note": "本页为中文镜像站的介绍页,Mod Manager 本体与数据版权归 ow-mods 团队(MIT)。遇到管理器本身的问题请到官方 Discord 或仓库反馈。",
    "load.failed": "加载失败:",
    "page.title.index": "星际拓荒 MOD 数据库",
    "page.title.mods": "全部 MOD — 星际拓荒 MOD 数据库",
    "page.title.jams": "历届 Game Jam — 星际拓荒 MOD 数据库",
    "page.title.manager": "Mod Manager — 星际拓荒 MOD 数据库",
    "page.title.notfound": "页面不存在 — 星际拓荒 MOD 数据库",
    "backTop": "回到顶部"
  },
  "ja": {
    "site.name": "アウターワイルズ MOD データベース",
    "brand": "アウターワイルズ MOD",
    "a11y.skip": "メインコンテンツへ移動",
    "a11y.nav": "メインナビ",
    "nav.mods": "すべてのMOD",
    "nav.jams": "過去のJam",
    "nav.manager": "Mod Manager",
    "home.title": "アウターワイルズ MOD",
    "home.intro1": "『Outer Wilds』の非公式MODで、新機能・改善・追加コンテンツを追加できます。",
    "home.intro2": "を使えば簡単にダウンロード・インストールできます。",
    "home.total": "現在 {n} 個のMOD・拡張・ツールがあります。",
    "home.syncInfo": "データ同期 {t} UTC · 概要 {done}/{total} 件翻訳済み",
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
    "footer.legal1": "非公式翻訳ミラーサイト · データ提供:",
    "footer.legal2": "· データベース(MIT) © ow-mods · MODメタデータの著作権は各作者に帰属 · AI自動翻訳(人間の校訂を随時反映)",
    "footer.mirror": "非公式翻訳ミラーサイト",
    "footer.home": "ホーム",
    "footer.dbHint1": "Mod Manager の Database URL に",
    "footer.dbUrl": "https://dslsdzc.github.io/ow-mod-db/data/ja/database.json",
    "footer.dbHint2": "を設定すると、ゲーム内で日本語の概要が使えます",
    "footer.repo": "GitHub リポジトリ",
    "footer.tagline": "概要の自動翻訳 · 更新:",
    "mods.title": "すべてのMOD",
    "mods.search": "MOD名・概要を検索…（英語名にも対応）",
    "mods.searchLabel": "MODを検索",
    "mods.sortLabel": "並び替え",
    "mods.sort.installs": "人気順",
    "mods.sort.newest": "新しい順",
    "mods.sort.updated": "更新順",
    "mods.sort.name": "名前順",
    "mods.allTag": "すべて",
    "mods.count": "{n} / {m} 個のMOD",
    "mods.none": "該当するMODがありません",
    "meta.downloads": "{n} 回DL",
    "meta.updatedAt": "更新 {d}",
    "detail.notFound": "このMODは見つかりませんでした。",
    "detail.notFoundTitle": "見つかりません",
    "detail.backList": "一覧に戻る",
    "detail.desc": "概要",
    "detail.latestRelease": "最新版の更新内容",
    "detail.addons": "付属MOD・バリエーション",
    "detail.releaseHistory": "更新履歴",
    "detail.patchSection": "中国語対応",
    "detail.comments": "コメント",
    "detail.commentsHint": "コメントは GitHub Discussions を利用しています · 英語のコメントはブラウザ翻訳で読めます",
    "detail.downloadZip": "zip をダウンロード",
    "detail.repoLink": "ソースリポジトリ",
    "detail.install": "ワンクリックでインストール",
    "detail.installHint": "Outer Wilds Mod Manager が必要です",
    "detail.reportIssue": "翻訳の問題を報告",
    "detail.share": "共有",
    "detail.copied": "リンクをコピーしました",
    "trend.title": "ダウンロード推移",
    "trend.loading": "推移を読み込み中…",
    "trend.failed": "推移データを取得できませんでした",
    "trend.noData": "このMODの推移データはまだありません（統計集計中）",
    "trend.viewOnOfficial": "公式サイトで見る",
    "trend.source": "データ提供: outerwildsmods.com",
    "readme.libMissing": "描画ライブラリを読み込めませんでした(CDN到達不可)。",
    "readme.openRepo": "リポジトリの原文を開く",
    "readme.aiNote": "翻訳はAIによるものです · 原文の著作権は作者に帰属します\u00a0·\u00a0{lic}",
    "readme.backTranslation": "翻訳に戻る",
    "readme.viewOriginal": "英語原文を表示",
    "readme.originalNote": "英語原文 · 原文の著作権は作者に帰属します",
    "readme.msView": "翻訳",
    "readme.msLoading": "翻訳中…",
    "readme.msFailed": "翻訳に失敗",
    "readme.msResult": "即時翻訳結果 · {base}",
    "readme.msFailedMsg": "翻訳に失敗: {msg}（ブラウザの翻訳機能もお試しください）",
    "readme.msHint": "{lic} ライセンス · 翻訳を生成中。「翻訳」で即時閲覧できます（保存されません）",
    "readme.msOnlyOnce": "今回のみ表示・保存されません",
    "readme.msCopyright": "原文の著作権は作者に帰属 · 今回の閲覧のみ、保存されません",
    "readme.licenseNone": "未表明(All Rights Reserved)",
    "readme.noLicenseHint": "リポジトリのライセンスは {lic} のため翻訳は保存されません。下のボタンは即時翻訳で、今回の閲覧のみです（保存されません）",
    "readme.fetchFailed": "READMEの読み込みに失敗:",
    "readme.loadFailed": "読み込みに失敗:",
    "patch.install": "パッチをワンクリックでインストール",
    "patch.download": "パッチをダウンロード",
    "patch.hint": "ダウンロードして Mods フォルダに入れるか、OWMM で zip をインストールしてください。",
    "patch.note": "パッチはコミュニティ制作物です。著作権は作者に帰属します。",
    "releases.original": "英語原文",
    "releases.translation": "日本語訳",
    "releases.translateAll": "すべて翻訳",
    "releases.showAll": "全 {n} 件のバージョンを表示",
    "jams.title": "歴代 Game Jam",
    "jams.works": "{n} 作品",
    "jams.placeholder": "Jam参加MODを認識できませんでした",
    "jams.fallbackTitle": "その他のJam作品",
    "jams.missingTitle": "歴代Jam（情報募集中）",
    "jams.intro": "アウターワイルズのコミュニティでは定期的にMOD制作Jamが開催されています。ここでは参加MODを回ごとに自動集計しています（公式データベースのタグと命名から識別）。並び順は人気順です。",
    "jams.groupNote": "翻訳は公式Jamページに基づき作成しました。著作権は主催者に帰属します。参加作品リストは自動集計です。",
    "jams.officialLink": "公式ページ",
    "jams.officialPage": "公式Jamページ",
    "jams.toOfficial": "公式ページへ",
    "jams.renderFailed": "Jamページの表示に失敗:",
    "notfound.msg": "ページが存在しません(404)……量子の状態に隠されているのかもしれません。",
    "notfound.home": "ホームに戻る",
    "notfound.browse": "すべてのMODを見る",
    "manager.title": "Outer Wilds Mod Manager(OWMM)",
    "manager.intro": "公式のMODマネージャー:MODのワンクリックダウンロード・インストール・更新、ゲーム内翻訳の管理、OWMLフレームワークの導入ができます。本サイト(日本語ミラー)のデータをそのまま利用できます。",
    "manager.dlTitle": "ダウンロードとインストール",
    "manager.dlStep1": "1. 公式リリースページから最新版(Windows ポータブル版またはインストーラー版)をダウンロードし、展開して実行します。",
    "manager.dlStep2": "2. OWMLフレームワークは自動でインストールされます。初回起動時にゲームのインストール先を選択してください。",
    "manager.dlLink": "公式ダウンロードページ",
    "manager.officialPage": "公式サイト",
    "manager.useTitle": "本サイトのデータベースを使う",
    "manager.useStep1": "Mod Manager で 設定(歯車) → Advanced を開き、Database URL を本サイトのアドレスに変更すると、ゲーム内で日本語の概要が表示されます:",
    "manager.useNote": "以後、マネージャー起動時に本サイトの最新データが自動チェックされます(約30分ごとに上流と同期、新規MODは自動翻訳)。",
    "manager.noteTitle": "補足",
    "manager.note": "このページは日本語ミラーサイトの案内です。Mod Manager 本体とデータの著作権は ow-mods チームに帰属します(MIT)。マネージャー自体の問題は公式の Discord またはリポジトリへ。",
    "load.failed": "読み込みに失敗:",
    "page.title.index": "アウターワイルズ MOD データベース",
    "page.title.mods": "すべてのMOD — アウターワイルズ MOD データベース",
    "page.title.jams": "歴代 Game Jam — アウターワイルズ MOD データベース",
    "page.title.manager": "Mod Manager — アウターワイルズ MOD データベース",
    "page.title.notfound": "ページが存在しません — アウターワイルズ MOD データベース",
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
  // 当前界面语言对应的数据目录代码(zh_cn 数据在根 data/ 下,其余在 data/<code>/ 下)
  const LANG_DIR = { "zh-CN": "zh_cn", ja: "ja" };
  window.LANG_DIR_CODE = LANG_DIR[lang] || "zh_cn";

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
    document.querySelectorAll("[data-i18n-aria-label]").forEach((el) => {
      const v = window.t(el.dataset.i18nAriaLabel);
      if (v) el.setAttribute("aria-label", v);
    });
    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
      const v = window.t(el.dataset.i18nTitle);
      if (v) el.setAttribute("title", v);
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
  // Turbo 无刷新导航后: 新 body 需要重新应用语言与语言切换器
  document.addEventListener("turbo:load", () => {
    apply();
    addLangSwitcher();
  });
})();
