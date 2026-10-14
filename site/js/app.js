// zh_cn 数据在根 data/ 下,其余语言在 data/<lang_dir>/ 下;统一带 DATA_V 缓存戳
function contentUrl(name) {
  const base = (window.LANG_DIR_CODE === "zh_cn") ? "data/" : "data/" + window.LANG_DIR_CODE + "/";
  return base + name + "?v=" + (window.DATA_V || "");
}

async function loadMods() {
  return fetchContent("mods.json");
}

function esc(s) {
  const div = document.createElement("div");
  div.textContent = String(s == null ? "" : s);
  return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function normLines(s) {
  return String(s == null ? "" : s).replace(/\r\n?/g, "\n");
}

function thumbUrl(m) {
  return m.thumbnail && m.thumbnail.main
    ? "https://ow-mods.github.io/ow-mod-db/thumbnails/" + m.thumbnail.main
    : "";
}

const THUMB_BG = { "1/1": "png/1to1.webp", "16/9": "png/16to9.webp", "21/9": "png/21to9.webp" };

function ratioKey(w, h) {
  const r = w / h;
  if (r < 1.3) return "1/1";
  if (r < 2.1) return "16/9";
  return "21/9";
}

function setupThumbBox(box) {
  const img = box.querySelector("img");
  if (!img) return;
  const apply = () => {
    if (!img.naturalWidth) return;
    const k = ratioKey(img.naturalWidth, img.naturalHeight);
    box.style.aspectRatio = k;
    box.style.backgroundImage = `url("${THUMB_BG[k]}")`;
  };
  if (img.complete && img.naturalWidth) apply();
  else img.addEventListener("load", apply);
}

function setupAllThumbs(root) {
  [...(root || document).querySelectorAll(".thumb-box")].forEach(setupThumbBox);
}

// ---- 缩略图预载策略: 首屏若干张直接加载,其余在进入视口前固定约 1.5 屏预载(慢网下浏览器自带 lazy 的提前量会收缩) ----
const THUMB_EAGER_N = 9;
let thumbObserver = null;

function setupLazyThumbs(root) {
  const imgs = [...(root || document).querySelectorAll("img[data-src]")];
  if (!imgs.length) return;
  if (!("IntersectionObserver" in window)) {
    imgs.forEach((img) => { img.src = img.getAttribute("data-src"); img.removeAttribute("data-src"); });
    return;
  }
  if (!thumbObserver) {
    thumbObserver = new IntersectionObserver((entries) => {
      for (const en of entries) {
        if (!en.isIntersecting) continue;
        const img = en.target;
        const src = img.getAttribute("data-src");
        if (src) { img.src = src; img.removeAttribute("data-src"); }
        thumbObserver.unobserve(img);
      }
    }, { rootMargin: "1200px 0px" });
  }
  imgs.forEach((img) => thumbObserver.observe(img));
}

function cardHtml(m, idx) {
  const thumb = thumbUrl(m);
  const img = !thumb ? ""
    : ((idx || 0) < THUMB_EAGER_N
      ? `<img src="${esc(thumb)}" alt="" loading="eager" fetchpriority="high" decoding="async">`
      : `<img data-src="${esc(thumb)}" alt="" decoding="async">`);
  const visual = thumb
    ? `<span class="thumb-box">${img}</span>`
    : `<span class="thumb-box ph-thumb" style="background-image:url('png/16to9.webp')"><span class="ph-text">${esc(m.name || m.uniqueName || "?")}</span></span>`;
  return `<a class="mod-card" href="mod/${encodeURIComponent(m.uniqueName)}.html">
    ${visual}
    <h3>${esc(m.name)}</h3>
    <div class="meta">${esc(m.authorDisplay)} · v${esc(m.version)} · ${window.t ? t("meta.downloads", { n: m.downloadCount }) : (m.downloadCount + " 次下载")}</div>
    <p class="desc">${esc(m.description)}</p>
  </a>`;
}

function installs(m) {
  return (m.installCount || 0) || (m.downloadCount || 0);
}

function sortMods(mods, mode) {
  const copy = [...mods];
  if (mode === "installs") {
    return copy.sort((a, b) => installs(b) - installs(a));
  }
  if (mode === "updated") {
    return copy.sort((a, b) => String(b.latestReleaseDate).localeCompare(String(a.latestReleaseDate)));
  }
  if (mode === "newest") {
    return copy.sort((a, b) => String(b.firstReleaseDate).localeCompare(String(a.firstReleaseDate)));
  }
  if (mode === "name") {
    return copy.sort((a, b) => String(a.name).localeCompare(String(b.name), "zh-Hans-CN"));
  }
  if (mode === "popularNew") {
    const cutoff = Date.now() - 60 * 24 * 3600 * 1000;
    const recent = copy.filter((m) => m.firstReleaseDate && new Date(m.firstReleaseDate).getTime() >= cutoff);
    return recent.sort((a, b) => installs(b) - installs(a));
  }
  return copy;
}

function jamKey(m) {
  const u = (m.uniqueName || "") + " " + (m.name || "");
  const hit = u.match(/(?:^|[._\sA-Za-z])(?:OW)?(?:Mod)?Jam\s*(\d+)/i);
  return hit ? "jam" + hit[1] : (/jam/i.test(u) ? "other" : "");
}

function renderJams(mods) {
  const root = document.getElementById("jams");
  if (!root) return;
  try {
  Promise.all([
    fetchContent("jams.json").catch(() => ({})),
    fetchContent("jam_content.json").catch(() => ({})),
  ]).then(([cfg, content]) => {
    cfg = cfg || {};
    content = content || {};
    const overrides = cfg.overrides || {};
    const buckets = new Map();
    const byId = new Map(mods.map((m) => [m.uniqueName, m]));
    const add = (k, m) => {
      if (!buckets.has(k)) buckets.set(k, []);
      buckets.get(k).push(m);
    };
    // 无人工成员表(key 无 members)的才用自动识别,保证届次计数与官方一致
    for (const m of mods) {
      const k = jamKey(m);
      if (!k) continue;
      const curated = content[k] && content[k].members;
      if (!curated) add(k, m);
    }
    for (const [k, c] of Object.entries(content)) {
      for (const uid of (c && c.members) || []) {
        const m = byId.get(uid);
        if (m) add(k, m);
      }
    }
    const entries = [...buckets.entries()]
      .sort((a, b) => (parseInt(b[0].replace("jam", "")) || 0) - (parseInt(a[0].replace("jam", "")) || 0));
    if (!entries.length) {
      root.innerHTML = `<p class="placeholder">${window.t ? t("jams.placeholder") : "暂未识别到 Jam 参赛 mod"}</p>`;
      return;
    }
    // 历届索引:每个大赛一个跳转 chip(分组锚点或信息页锚点)
    const navHtml = (content.index || []).map((it) => {
      const hasPage = it.page && (content.pages || {})[it.page];
      const hasBucket = it.key && entries.some(([k]) => k === it.key);
      const label = (it.now ? "▶ " : "") + it.label;
      if (hasPage) {
        return `<button class="chip" data-scroll="sec-${esc(it.page)}">${esc(label)}</button>`;
      }
      if (hasBucket) {
        return `<button class="chip" data-scroll="${esc(it.key)}">${esc(label)}</button>`;
      }
      return `<a class="chip" href="${esc(it.url)}" target="_blank" rel="noopener">${esc(label)}</a>`;
    }).join("") || "";
    const titleOf = (k) => {
      if (content[k] && content[k].name) return content[k].name;
      if (overrides[k] && overrides[k].name) return overrides[k].name;
      if (k === "other") return (cfg.fallbackTitle || (window.t ? t("jams.fallbackTitle") : "其他 Jam 作品"));
      return window.t ? t("jams.missingTitle") : "历届 Jam 届次(待补充)";   // 不做数字编号,保持可扩展
    };
    root.innerHTML = entries.map(([k, list]) => {
      list.sort((a, b) => installs(b) - installs(a));
      const o = overrides[k] || {};
      const c = content[k] || {};
      const sections = (c.sections || []).map((s, i) =>
        `<div class="jam-sec"><h3>${esc(s.h)}</h3><div class="readme jam-md-${k}-${i}"></div></div>`).join("");
      return `<section class="home-section" data-jam="${esc(k)}">
        <h2>${esc(titleOf(k))} <span class="meta">· ${window.t ? t("jams.works", { n: list.length }) : (list.length + " 个作品")}</span></h2>
        ${c.introZh ? `<div class="readme" data-bucket-md="${esc(k)}"></div>` : ""}
        ${(c.officialUrl || o.officialUrl) ? `<p><a class="link" href="${esc(c.officialUrl || o.officialUrl)}" target="_blank" rel="noopener">${window.t ? t("jams.officialLink") : "官方届次页面"}</a></p>` : ""}
        ${sections}
        ${c.sections && c.sections.length ? `<p class="foot-note">${window.t ? t("jams.groupNote") : "译文依据官方 Jam 页面撰写,版权归主办方;参赛作品列表为本站自动聚合。"}</p>` : ""}
        <div class="grid">${list.map((m) => cardHtml(m, THUMB_EAGER_N)).join("")}</div>
      </section>`;
    }).join("");
    // 跳转条必须在 innerHTML 之后插入(否则会被覆盖)
    if (navHtml) {
      const nav = document.createElement("div");
      nav.className = "chips";
      nav.innerHTML = navHtml;
      nav.addEventListener("click", (e) => {
        const b = e.target.closest("[data-scroll]");
        if (!b) return;
        const key = b.dataset.scroll;
        const sec = key.startsWith("sec-")
          ? root.querySelector(`[data-page="${key.slice(4)}"]`)
          : root.querySelector(`section[data-jam="${key}"]`);
        if (sec) {
          const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          sec.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
        }
      });
      root.prepend(nav);
    }
    setupAllThumbs(root);
    setupLazyThumbs(root);
    // 分组简介与章节正文: 统一走 markdown(保列表/换行),按组作用域查找
    root.querySelectorAll("[data-bucket-md]").forEach((el) => {
      const c = content[el.dataset.bucketMd];
      if (c && c.introZh) renderMarkdownInto(el, c.introZh, "", true);
    });
    root.querySelectorAll(".jam-sec .readme").forEach((el) => {
      const parts = el.className.match(/jam-md-(.+)-(\d+)$/);
      if (!parts) return;
      const c = content[parts[1]];
      const sec = c && c.sections && c.sections[Number(parts[2])];
      if (sec && sec.md) renderMarkdownInto(el, sec.md, "", true);
    });
    // 独立信息页(如 2026 Game Jam,无本地参赛分组)
    const pagesHtml = Object.entries(content.pages || {}).map(([pk, p]) => `
      <section class="home-section jam-sec" data-page="${esc(pk)}">
        <h2>${esc(p.titleZh || "")}</h2>
        <div class="readme" data-page-md></div>
        <div class="cta-row" style="margin-top:.6rem;">
          <a class="cta" href="${esc(p.url || "#")}" target="_blank" rel="noopener">${esc(p.urlLabelZh || (window.t ? t("jams.toOfficial") : "前往官方页面"))}</a>
        </div>
        ${(p.sections || []).map((s, i) => `<div class="jam-sec"><h3>${esc(s.h)}</h3><div class="readme" data-page-sec="${pk}-${i}"></div></div>`).join("")}
        <p class="foot-note">${window.t ? t("jams.groupNote") : "译文依据官方 Jam 页面撰写,版权归主办方。"}</p>
      </section>`).join("");
    if (pagesHtml) root.insertAdjacentHTML("beforeend", pagesHtml);
    // 信息页正文:按页作用域填充,避免全局选择器错位
    Object.entries(content.pages || {}).forEach(([pk, p]) => {
      const sec = root.querySelector(`[data-page="${pk}"]`);
      if (!sec) return;
      const mdBox = sec.querySelector("[data-page-md]");
      if (mdBox && p.introZh) renderMarkdownInto(mdBox, p.introZh, "", true);
      (p.sections || []).forEach((s, i) => {
        const box = sec.querySelector(`[data-page-sec="${pk}-${i}"]`);
        if (box && s.md) renderMarkdownInto(box, s.md, "", true);
      });
    });
  }).catch((err) => {
    root.innerHTML = `<p class="placeholder">${window.t ? t("jams.renderFailed") : "Jam 页渲染失败:"}${esc(err && err.message ? err.message : String(err))}</p>`;
  });
  } catch (e) {
    root.innerHTML = `<p class="placeholder">${window.t ? t("jams.renderFailed") : "Jam 页渲染失败:"}${esc(e && e.message ? e.message : String(e))}</p>`;
  }
}

function renderHome(mods) {
  const total = document.getElementById("mod-total");
  if (total) total.textContent = window.t ? t("home.total", { n: mods.length }) : `目前共有 ${mods.length} 个 MOD、扩展与工具。`;
  const featured = document.getElementById("featured");
  if (!featured) return;
  const sections = [
    ["home.popular", "installs"],
    ["home.popularNew", "popularNew"],
    ["home.updated", "updated"],
  ];
  featured.innerHTML = sections.map(([title, mode]) => {
    const items = sortMods(mods, mode).slice(0, 3);
    return `<section><h2>${window.t ? t(title) : title}</h2><div class="grid">${items.map(cardHtml).join("")}</div></section>`;
  }).join("");
  setupAllThumbs(featured);
  setupLazyThumbs(featured);
}

function renderList(mods) {
  const grid = document.getElementById("mod-grid");
  const search = document.getElementById("search");
  const sort = document.getElementById("sort");
  const chipsEl = document.getElementById("tag-chips");
  const count = document.getElementById("count");
  if (!grid) return;

  let tag = "";

  const allTags = [...new Set(mods.flatMap((m) => m.tags || []))].sort();
  if (chipsEl) {
    const mk = (label, value) => {
      const b = document.createElement("button");
      b.className = "chip";
      b.textContent = label;
      b.dataset.tag = value;
      b.onclick = () => { tag = tag === value ? "" : value; refreshChips(); draw(); };
      chipsEl.appendChild(b);
      return b;
    };
    mk(window.t ? t("mods.allTag") : "全部", "");
    for (const t of allTags) mk(t, t);
    refreshChips();  // 初始 "全部" 处于选中态(并同步 aria-pressed)
  }
  function refreshChips() {
    if (!chipsEl) return;
    [...chipsEl.children].forEach((b) => {
      const on = b.dataset.tag === tag;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", String(on));
    });
  }

  function draw() {
    const q = search.value.trim().toLowerCase();
    const mode = sort ? sort.value : "installs";
    let shown = mods.filter((m) => {
      if (tag && !(m.tags || []).includes(tag)) return false;
      if (!q) return true;
      return (m.name + " " + (m.originalName || "") + " " + m.description + " " + m.authorDisplay).toLowerCase().includes(q);
    });
    shown = sortMods(shown, mode);
    count.textContent = (window.t ? t("mods.count", { n: shown.length, m: mods.length }) : (shown.length + " / " + mods.length + " 个 MOD"));
    grid.innerHTML = shown.map(cardHtml).join("") || `<p class="placeholder">${window.t ? t("mods.none") : "没有匹配的 MOD"}</p>`;
    setupAllThumbs(grid);
    setupLazyThumbs(grid);
  }

  let searchTimer = 0;
  search.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(draw, 120);  // 防抖: 快速输入时避免每次按键都重建列表
  });
  if (sort) sort.addEventListener("change", draw);
  draw();
}

async function fetchJson(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(url + " " + resp.status);
  return resp.json();
}

// 先所选语言目录,404/缺失时回退官方英文(data/en/)——zh_cn 根目录即中文,无需第二跳
async function fetchContent(name) {
  const resp = await fetch(contentUrl(name));
  if (resp.ok) return resp.json();
  const respEn = await fetch("data/en/" + name + "?v=" + (window.DATA_V || ""));
  if (respEn.ok) return respEn.json();
  throw new Error("content 加载失败: " + name);
}

// ---- 按需翻译: 微软 Edge 免费端点(KISS Translator 同源实现,免鉴权,浏览器直连) ----
async function msTranslateTexts(texts, to) {
  if (!texts.length) return [];
  const url = "https://edge.microsoft.com/translate/translatetext?from=&to="
    + encodeURIComponent(to || "zh-Hans") + "&isEnterpriseClient=false";
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(texts),
  });
  if (!resp.ok) throw new Error("翻译服务 " + resp.status);
  const data = await resp.json();
  return data.map((item) => (item.translations || []).map((t) => t.text).join(" "));
}

let mermaidLoad = null;   // mermaid(~3MB) 按需加载: 仅页面真含图表时才拉取, 不拖慢所有详情页

function ensureMermaid() {
  if (window.mermaid) return Promise.resolve();
  if (!mermaidLoad) {
    mermaidLoad = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js";
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }
  return mermaidLoad;
}

async function renderMermaidBlocks(scope) {
  const blocks = [...(scope || document).querySelectorAll("pre > code.language-mermaid")];
  if (!blocks.length) return;                        // 无图表: 完全不加载
  try { await ensureMermaid(); } catch (e) { return; }   // 加载失败: 保留代码块原文
  mermaid.initialize({ startOnLoad: false, theme: "dark" });
  blocks.forEach(async (code) => {
    try {
      const id = "mmd-" + Math.random().toString(36).slice(2, 9);
      const svg = await mermaid.render(id, code.textContent);
      const pre = code.closest("pre");
      pre.outerHTML = svg;
    } catch (e) {
      // 图语法错误则保留代码原文展示
    }
  });
}

function initSlugMap(mods) {
  window.__slugMap = {};
  for (const m of mods) {
    if (m.slug) window.__slugMap[m.slug] = m.uniqueName;
  }
}

// 内容(简介/更新说明/README)里指向官方 mod 详情页的链接 → 改写回本站详情页
function rewriteOfficialModLinks(scope) {
  const slugMap = window.__slugMap;
  if (!slugMap) return;
  [...(scope || document).querySelectorAll("a[href]")].forEach((a) => {
    const h = a.getAttribute("href") || "";
    const m = h.match(/^https?:\/\/outerwildsmods\.com\/mods\/([^/?#]+)/);
    if (!m) return;
    const uid = slugMap[m[1]];
    if (uid) {
      a.href = "mod/" + encodeURIComponent(uid) + ".html";
      a.removeAttribute("target");
    }
  });
}

function renderMarkdownInto(el, md, baseUrl, breaks) {
  if (!window.marked || !window.DOMPurify) {
    el.innerHTML = `<p class="placeholder">${window.t ? t("readme.libMissing") : "渲染库未加载(CDN 不可达)," }<a class="link" href="${esc(baseUrl)}" target="_blank" rel="noopener">${window.t ? t("readme.openRepo") : "打开仓库原文目录"}</a></p>`;
    return;
  }
  const raw = marked.parse(md, { gfm: true, breaks: !!breaks });
  el.innerHTML = DOMPurify.sanitize(raw);
  renderMermaidBlocks(el);
  // 加载失败的图(如徽章图无法访问)直接隐藏,不显示 alt 文本噪音; 懒加载避免一次性拉取大量图片
  el.querySelectorAll("img").forEach((img) => {
    img.loading = "lazy";
    img.decoding = "async";
    img.addEventListener("error", () => { img.style.visibility = "hidden"; }, { once: true });
  });
  // 相对路径图片/链接补全为 raw 绝对地址
  if (baseUrl) {
    el.querySelectorAll("img[src]").forEach((img) => {
      const s = img.getAttribute("src") || "";
      if (!/^(https?:|data:)/i.test(s) && !s.startsWith("#")) {
        img.src = baseUrl + s.replace(/^\.\//, "");
      }
    });
    el.querySelectorAll("a[href]").forEach((a) => {
      const h = a.getAttribute("href") || "";
      if (!/^(https?:|mailto:|#)/i.test(h)) {
        a.href = baseUrl + h.replace(/^\.\//, "");
        a.target = "_blank";
        a.rel = "noopener";
      }
    });
  }
  // 官方 mod 页链接改写必须在 base 补全之后,否则刚生成的本站内部链接会被前缀成 raw 地址
  rewriteOfficialModLinks(el);
}

function initPatchBlock(mod) {
  const section = document.getElementById("patch-section");
  const box = document.getElementById("patch-box");
  if (!section || !box) return;
  fetchContent("patches.json")
    .then((patches) => {
      const p = patches[mod.uniqueName];
      if (!p) { section.remove(); return; }
      section.hidden = false;
      const installBtn = p.install === "owmm" && p.uniqueName
        ? `<a class="cta" href="owmods://install-mod/${encodeURIComponent(p.uniqueName)}"
             title="${window.t ? t("detail.installHint") : "需已安装 Outer Wilds Mod Manager"}">${window.t ? t("patch.install") : "一键安装补丁"}</a>`
        : (p.url ? `<a class="cta" href="${esc(p.url)}" target="_blank" rel="noopener">${window.t ? t("patch.download") : "下载补丁"}</a>` : "");
      const manualNote = p.install === "manual"
        ? `<p class="foot-note">${window.t ? t("patch.hint") : "下载后放入 Mods 文件夹,或用 OWMM 安装 zip。"}</p>` : "";
      box.innerHTML =
        `<div><p style="margin:0 0 .4rem;">${esc(p.name || (window.t ? t("detail.patchSection") : "中文支持"))}</p>
         <div class="cta-row">${installBtn}</div>
         ${p.note ? `<p class="foot-note">${esc(p.note)}</p>` : ""}
         ${manualNote}
         <p class="foot-note">${window.t ? t("patch.note") : "补丁为社区作品,版权归作者所有。"}</p></div>`;
    })
    .catch(() => section.remove());
}

function initReleases(mod) {
  const section = document.getElementById("releases-section");
  const list = document.getElementById("releases-list");
  if (!section || !list) return;
  fetchContent("releases/" + encodeURIComponent(mod.uniqueName) + ".json")
    .then((data) => {
      const rels = (data && data.releases) || [];
      if (!rels.length) { section.remove(); return; }
      section.hidden = false;
      const SHOW = 5;
      const msCache = new Map();     // 版本索引 -> 微软即时译文(仅本次阅读,不保存)
      let currentItems = [];
      const isTranslated = (i, r) => !!(r.bodyZh || msCache.has(i));

      const allBtn = document.getElementById("releases-translate-all");
      const updateTranslateAll = () => {
        if (!allBtn) return;
        allBtn.hidden = !rels.some((r, i) => r.body && !isTranslated(i, r));
      };

      function renderItems(items) {
        currentItems = items;
        const itemHtml = (r) => {
          const gi = rels.indexOf(r);
          const done = isTranslated(gi, r);
          return `<div class="rel-item">
          <div class="rel-head">
            <a class="rel-tag" href="${esc(r.zipUrl || r.releaseUrl || "#")}" target="_blank" rel="noopener">${esc(r.tag)}</a>
            <span class="rel-meta">${esc(r.name !== r.tag ? r.name : "")} · ${esc(r.date)}</span>
            ${r.zipUrl ? `<a class="rel-zip" href="${esc(r.zipUrl)}" target="_blank" rel="noopener">zip</a>` : ""}
            ${r.body ? `<button class="chip rel-tr" data-showing="${done ? "translation" : "original"}">${done ? (window.t ? t("releases.original") : "原文") : (window.t ? t("readme.msView") : "翻译")}</button>` : ""}
          </div>
          ${r.body ? `<div class="readme rel-body"></div>` : ""}
        </div>`;
        };
        list.innerHTML = items.map(itemHtml).join("");
        [...list.querySelectorAll(".rel-item")].forEach((el, i) => {
          const r = items[i];
          const gi = rels.indexOf(r);
          const bodyEl = el.querySelector(".rel-body");
          const btn = el.querySelector(".rel-tr");
          if (!r || !r.body) return;
          renderMarkdownInto(bodyEl, msCache.get(gi) || r.bodyZh || r.body, "");
          if (btn) {
            btn.onclick = async () => {
              if (btn.classList.contains("busy")) return;
              if (btn.dataset.showing === "translation") {
                // 译文 → 英文原文
                renderMarkdownInto(bodyEl, r.body, "");
                btn.dataset.showing = "original";
                btn.textContent = (r.bodyZh || msCache.has(gi))
                  ? (window.t ? t("releases.translation") : "中文译文")
                  : (window.t ? t("readme.msView") : "翻译");
                return;
              }
              const cached = msCache.get(gi) || r.bodyZh;
              if (cached) {
                // 已有现成译文(预翻译或已即时翻译过) → 直接切回, 不重复请求机翻
                renderMarkdownInto(bodyEl, cached, "");
                btn.dataset.showing = "translation";
                btn.textContent = window.t ? t("releases.original") : "原文";
                return;
              }
              btn.classList.add("busy");
              btn.textContent = window.t ? t("readme.msLoading") : "翻译中…";
              try {
                const zh = await msTranslateTexts([r.body]);
                msCache.set(gi, zh[0] || r.body);
                renderMarkdownInto(bodyEl, zh[0] || r.body, "");
                btn.dataset.showing = "translation";
                btn.textContent = window.t ? t("releases.original") : "原文";
                updateTranslateAll();
              } catch (e) {
                btn.textContent = window.t ? t("readme.msFailed") : "翻译失败";
              } finally {
                btn.classList.remove("busy");
              }
            };
          }
        });
      }

      if (allBtn) {
        allBtn.onclick = async () => {
          if (allBtn.classList.contains("busy")) return;
          allBtn.classList.add("busy");
          const origin = window.t ? t("releases.translateAll") : "全部翻译";
          allBtn.textContent = window.t ? t("readme.msLoading") : "翻译中…";
          try {
            const todo = rels.map((r, i) => ({ r, i })).filter(({ r, i }) => r.body && !isTranslated(i, r));
            for (let s = 0; s < todo.length;) {
              const group = [];
              let glen = 0;
              while (s < todo.length && group.length < 4 && (glen === 0 || glen + todo[s].r.body.length <= 4000)) {
                group.push(todo[s]);
                glen += todo[s].r.body.length;
                s++;
              }
              const zhArr = await msTranslateTexts(group.map(({ r }) => r.body));
              group.forEach(({ r, i }, k) => {
                if (!zhArr[k]) return;
                msCache.set(i, zhArr[k]);
                const ci = currentItems.indexOf(r);
                if (ci < 0) return;
                const el = list.querySelectorAll(".rel-item")[ci];
                const bodyEl = el && el.querySelector(".rel-body");
                if (bodyEl) renderMarkdownInto(bodyEl, zhArr[k], "");
                const btn = el && el.querySelector(".rel-tr");
                if (btn) {
                  btn.dataset.showing = "translation";
                  btn.textContent = window.t ? t("releases.original") : "原文";
                }
              });
            }
            allBtn.textContent = origin;
          } catch (e) {
            allBtn.textContent = window.t ? t("readme.msFailed") : "翻译失败";
            setTimeout(() => { allBtn.textContent = origin; }, 1500);
          } finally {
            allBtn.classList.remove("busy");
            updateTranslateAll();
          }
        };
      }

      const more = rels.length > SHOW;
      renderItems(more ? rels.slice(0, SHOW) : rels);
      if (more) {
        const btn = document.createElement("button");
        btn.className = "chip";
        btn.textContent = window.t ? t("releases.showAll", { n: rels.length }) : `显示全部 ${rels.length} 个版本`;
        btn.onclick = () => { renderItems(rels); btn.remove(); };
        list.appendChild(btn);
      }
      updateTranslateAll();
    })
    .catch(() => section.remove());
}

function initComments(mod) {
  const section = document.getElementById("comments-section");
  if (!section) return;
  section.hidden = false;
  if (document.getElementById("giscus-frame") || document.querySelector("#giscus script")) return;
  const script = document.createElement("script");
  script.src = "https://giscus.app/client.js";
  script.setAttribute("data-repo", "dslsdzc/ow-mod-db");
  script.setAttribute("data-repo-id", "R_kgDOULlpLw");
  script.setAttribute("data-category", "General");
  script.setAttribute("data-category-id", "DIC_kwDOULlpL84DEuQA");
  script.setAttribute("data-mapping", "specific");
  // 与官网同款: 讨论串标题 "mod: <uniqueName>" 预建在仓库 Discussions 里
  // (GitHub 限制每日预建数;未预建的串由首位评论者自动创建,strict=0 自愈)
  script.setAttribute("data-term", "mod: " + mod.uniqueName);
  script.setAttribute("data-strict", "0");
  script.setAttribute("data-reactions-enabled", "0");
  script.setAttribute("data-emit-metadata", "1");
  script.setAttribute("data-input-position", "top");
  script.setAttribute("data-theme", "dark");
  script.setAttribute("data-lang", "zh-CN");
  script.setAttribute("crossorigin", "anonymous");
  script.async = true;
  document.getElementById("giscus").appendChild(script);
}

function collectTextNodes(root) {
  const out = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!node.nodeValue || !node.nodeValue.trim()) continue;
    const parent = node.parentElement;
    if (parent && parent.closest("pre, code")) continue;  // 代码块不翻
    out.push(node);
  }
  return out;
}

// 先渲染英文 HTML,再只翻译文本节点 —— markdown 结构/链接/图片完全不受影响
async function translateReadmeDom(root) {
  const nodes = collectTextNodes(root);
  const batches = [];
  let cur = [], curLen = 0;
  for (const node of nodes) {
    const len = node.nodeValue.length;
    if (cur.length && curLen + len > 700) { batches.push(cur); cur = []; curLen = 0; }
    cur.push(node);
    curLen += len;
  }
  if (cur.length) batches.push(cur);
  for (const batch of batches) {
    const texts = batch.map((n) => n.nodeValue);
    const zh = await msTranslateTexts(texts);
    batch.forEach((n, i) => { if (zh[i]) n.nodeValue = zh[i]; });
  }
}

function initAddons(mod, allMods) {
  const wrap = document.getElementById("addons-section");
  if (!wrap) return;
  const children = allMods.filter((m) => m.parent === mod.uniqueName && m.uniqueName !== mod.uniqueName);
  const variations = (mod.repoVariations || []).map((v) => typeof v === "string" ? { uniqueName: v } : v)
    .filter((v) => v && (v.uniqueName || v.repo || v.repoUrl || v.name));
  if (!children.length && !variations.length) { wrap.remove(); return; }
  wrap.hidden = false;
  const list = document.getElementById("addons-list");
  const shortLabel = (s) => {
    if (!s) return "";
    const t = String(s);
    const m = t.match(/^https?:\/\/(?:www\.)?github\.com\/([^/]+\/[^/]+?)\/?$/);
    return m ? m[1] : t;
  };
  const card = (m, label) => `<a class="mod-card" href="${m.uniqueName && !/^https?:/.test(m.uniqueName)
      ? "mod/" + encodeURIComponent(m.uniqueName) + ".html"
      : (esc(m.repoUrl || m.repo || "#"))}" target="${m.uniqueName && !/^https?:/.test(m.uniqueName) ? "" : "_blank"}" rel="noopener">
      <div><h3>${esc(label || m.name || shortLabel(m.repo || m.repoUrl || m.uniqueName) || m.uniqueName)}</h3>
      <div class="meta">${esc(shortLabel(m.repo || m.repoUrl || m.uniqueName) || "")}</div></div></a>`;
  const html = [];
  for (const c of children) html.push(card(c, c.name || c.uniqueName));
  for (const v of variations) {
    html.push(card(v, v.name || shortLabel(v.uniqueName) || shortLabel(v.repo || v.repoUrl)));
  }
  list.innerHTML = `<div class="grid">${html.join("")}</div>`;
}

function initReadme(mod) {
  const section = document.getElementById("readme-section");
  if (!section || !mod.readmeDownloadUrl) return;
  section.hidden = false;
  const actions = document.getElementById("readme-actions");
  const content = document.getElementById("readme-content");
  const setHint = (text) => {
    // 只更新提示文字, 不清空容器(否则会把旁边注入的按钮一起销毁)
    let h = actions.querySelector("span.hint");
    if (!h) {
      h = document.createElement("span");
      h.className = "hint";
      actions.prepend(h);
    }
    h.textContent = text;
  };
  const baseUrl = mod.readmeDownloadUrl.slice(0, mod.readmeDownloadUrl.lastIndexOf("/") + 1);

  async function fetchEn() {
    const resp = await fetch(mod.readmeDownloadUrl);
    if (!resp.ok) throw new Error("README 抓取失败 " + resp.status);
    return resp.text();
  }

  function showMd(md) { renderMarkdownInto(content, md, baseUrl); }

  (async () => {
    try {
      const [readmes, licenses] = await Promise.all([
        fetchContent("readmes.json").catch(() => ({})),
        fetchContent("licenses.json").catch(() => ({})),
      ]);
      const zh = readmes[mod.uniqueName];
      const lic = licenses[mod.uniqueName] || "";
      const permissive = ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
                          "Unlicense", "0BSD", "MIT-0", "MPL-2.0"].includes(lic);

      if (zh && zh.zh) {
        setHint(window.t ? t("readme.aiNote", { lic }) : "译文由 AI 生成 · 原文版权归作者所有 · " + lic);
        showMd(zh.zh);
        // 两个显式按钮互相切换(比单按钮改文字更可靠,无状态残留)
        const zhBtn = document.createElement("button");
        zhBtn.textContent = window.t ? t("readme.backTranslation") : "回到中文译文";
        zhBtn.hidden = true;
        const enBtn = document.createElement("button");
        enBtn.textContent = window.t ? t("readme.viewOriginal") : "查看英文原文";
        const setActive = (zhActive) => {
          zhBtn.hidden = zhActive;    // 译文态: 隐藏"回到译文", 显示"查看原文"
          enBtn.hidden = !zhActive;
        };
        zhBtn.onclick = () => {
          showMd(zh.zh);
          setHint(window.t ? t("readme.aiNote", { lic }) : "译文由 AI 生成 · 原文版权归作者所有 · " + lic);
          setActive(true);
        };
        enBtn.onclick = async () => {
          if (enBtn.classList.contains("busy")) return;
          enBtn.classList.add("busy");
          try {
            showMd(await fetchEn());
            setHint(window.t ? t("readme.originalNote") : "英文原文 · 原文版权归作者所有");
            setActive(false);
          } catch (e) { setHint((window.t ? t("readme.loadFailed") : "加载失败:") + e.message); }
          finally { enBtn.classList.remove("busy"); }
        };
        actions.prepend(enBtn);
        actions.prepend(zhBtn);
        return;
      }
      // 无预翻译: 拉英文原文展示
      const md = await fetchEn();
      const addMsButton = (hintBase) => {
        const btn = document.createElement("button");
        btn.dataset.showing = "original";
        btn.textContent = window.t ? t("readme.msView") : "翻译";
        btn.onclick = async () => {
          if (btn.classList.contains("busy")) return;
          if (btn.dataset.showing === "translated") {
            // 当前显示微软翻译 → 切回英文原文
            showMd(md);
            setHint(window.t ? t("readme.originalNote") : "英文原文 · 原文版权归作者所有");
            btn.dataset.showing = "original";
            btn.textContent = window.t ? t("readme.msView") : "翻译";
            return;
          }
          btn.classList.add("busy");
          btn.textContent = window.t ? t("readme.msLoading") : "翻译中…";
          try {
            // 先渲染英文 HTML(链接/图片/代码块保持原样),再只翻译可见文本
            showMd(md);
            await translateReadmeDom(content);
            setHint(window.t ? t("readme.msResult", { base: hintBase }) : "即时翻译结果 · " + hintBase);
            btn.dataset.showing = "translated";
            btn.textContent = window.t ? t("readme.viewOriginal") : "查看英文原文";
          } catch (e) {
            setHint(window.t ? t("readme.msFailedMsg", { msg: e.message }) : "翻译失败:" + e.message + " (可换用浏览器自带翻译)");
            btn.dataset.showing = "original";
            btn.textContent = window.t ? t("readme.msView") : "翻译";
          } finally {
            btn.classList.remove("busy");
          }
        };
        actions.prepend(btn);
      };
      if (permissive) {
        setHint(window.t ? t("readme.msHint", { lic }) : lic + " 许可 · 译文生成中,可用「翻译」即时浏览(不保存)");
        showMd(md);
        addMsButton(window.t ? t("readme.msOnlyOnce") : "仅本次查看,不保存");
      } else {
        // 非开放许可(AGPL/GPL/无): 尊重版权不预翻不保存;
        // 但用户即时浏览性翻译等同于浏览器翻译,仍提供按钮
        setHint(window.t
          ? t("readme.noLicenseHint", { lic: lic === "none" ? t("readme.licenseNone") : lic })
          : "仓库许可为 " + (lic === "none" ? "未声明(保留所有权利)" : lic)
            + ",未保存译文;下方按钮为即时翻译,仅供本次阅读、不保存");
        showMd(md);
        addMsButton(window.t ? t("readme.msCopyright") : "原文版权归作者所有 · 仅本次阅读,不保存");
      }
    } catch (e) {
      setHint((window.t ? t("readme.fetchFailed") : "README 加载失败:") + e.message);
    }
  })();
}

function initShare(mod) {
  const btn = document.getElementById("share-btn");
  if (!btn) return;
  const label = btn.textContent;
  btn.addEventListener("click", async () => {
    const url = location.href.split("#")[0];
    const title = `${mod.name} — ${window.t ? t("site.name") : "星际拓荒 MOD 数据库"}`;
    if (navigator.share) {
      try { await navigator.share({ title, url }); return; } catch (e) { /* 取消或失败则走复制 */ }
    }
    try {
      await navigator.clipboard.writeText(url);
      btn.textContent = window.t ? t("detail.copied") : "已复制链接";
      setTimeout(() => { btn.textContent = label; }, 2000);
    } catch (e) {
      window.prompt(window.t ? t("detail.share") : "分享", url);
    }
  });
}

// ---- 下载趋势(页面末尾): 滚动到视口时才按需拉官方统计 API, 失败优雅降级 ----
function trendChartHtml(rows) {
  const pts = rows
    .filter((r) => r && typeof r.DownloadCount === "number" && typeof r.UnixTimestamp === "number")
    .sort((a, b) => a.UnixTimestamp - b.UnixTimestamp);
  const W = 720, H = 220, PL = 10, PR = 10, PT = 16, PB = 22;
  const xs = pts.map((p) => p.UnixTimestamp);
  const ys = pts.map((p) => p.DownloadCount);
  const x0 = xs[0], x1 = xs[xs.length - 1];
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  const sx = (t) => PL + (t - x0) / Math.max(1, x1 - x0) * (W - PL - PR);
  const sy = (v) => PT + (1 - (v - y0) / Math.max(1, y1 - y0)) * (H - PT - PB);
  const step = Math.max(1, Math.ceil(pts.length / 160));
  const sampled = pts.filter((_, i) => i % step === 0 || i === pts.length - 1);
  const line = sampled.map((p) => `${sx(p.UnixTimestamp).toFixed(1)},${sy(p.DownloadCount).toFixed(1)}`).join(" ");
  const first = sampled[0], last = sampled[sampled.length - 1];
  const area = `${sx(first.UnixTimestamp).toFixed(1)},${H - PB} ${line} ${sx(last.UnixTimestamp).toFixed(1)},${H - PB}`;
  const fmtDate = (t) => new Date(t * 1000).toISOString().slice(0, 10);
  const fmtNum = (v) => (v >= 10000 ? Math.round(v / 1000) + "k" : String(v));
  const html = `
    <svg class="trend-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${window.t ? t("trend.title") : "下载趋势"}">
      <defs><linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#ff9c86" stop-opacity="0.32"/>
        <stop offset="100%" stop-color="#ff9c86" stop-opacity="0.02"/>
      </linearGradient></defs>
      <polygon fill="url(#trend-fill)" points="${area}"/>
      <polyline fill="none" stroke="#ff9c86" stroke-width="2" points="${line}"/>
      <circle cx="${sx(last.UnixTimestamp).toFixed(1)}" cy="${sy(last.DownloadCount).toFixed(1)}" r="3" fill="#ff9c86"/>
      <text x="${PL}" y="${H - 6}" class="trend-axis">${fmtDate(first.UnixTimestamp)}</text>
      <text x="${W - PR}" y="${H - 6}" class="trend-axis" text-anchor="end">${fmtDate(last.UnixTimestamp)}</text>
      <text x="${W - PR}" y="${PT + 10}" class="trend-axis" text-anchor="end">${fmtNum(last.DownloadCount)}</text>
    </svg>
    <p class="trend-src">${window.t ? t("trend.source") : "数据来自 outerwildsmods.com"}</p>`;
  return { html, pts, geo: { W, H, PL, PR, PT, PB, x0, x1, sx, sy } };
}

function setupTrendInteractions(box, pts, geo) {
  const svg = box.querySelector("svg");
  if (!svg || !pts.length) return;
  const NS = "http://www.w3.org/2000/svg";
  const guide = document.createElementNS(NS, "line");
  guide.setAttribute("class", "trend-guide");
  guide.setAttribute("y1", geo.PT);
  guide.setAttribute("y2", geo.H - geo.PB);
  guide.style.display = "none";
  const dot = document.createElementNS(NS, "circle");
  dot.setAttribute("class", "trend-dot");
  dot.setAttribute("r", "4");
  dot.style.display = "none";
  svg.appendChild(guide);
  svg.appendChild(dot);
  const tip = document.createElement("div");
  tip.className = "trend-tip";
  tip.hidden = true;
  box.appendChild(tip);

  const fmtNum = (v) => Number(v).toLocaleString("en-US");
  const fmtDate = (t) => new Date(t * 1000).toISOString().slice(0, 10);
  let hideTimer = 0;
  const hide = () => {
    guide.style.display = "none";
    dot.style.display = "none";
    tip.hidden = true;
  };
  const scheduleHide = () => {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, 1400);
  };
  const show = (clientX) => {
    clearTimeout(hideTimer);
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const k = geo.W / rect.width;   // 屏幕像素 -> SVG 坐标
    const gx = Math.min(Math.max((clientX - rect.left) * k, geo.PL), geo.W - geo.PR);
    const when = geo.x0 + (gx - geo.PL) / (geo.W - geo.PL - geo.PR) * (geo.x1 - geo.x0);
    let lo = 0, hi = pts.length - 1;   // 二分找最近时间点
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (pts[mid].UnixTimestamp <= when) lo = mid; else hi = mid;
    }
    const p = Math.abs(pts[lo].UnixTimestamp - when) <= Math.abs(pts[hi].UnixTimestamp - when) ? pts[lo] : pts[hi];
    const px = geo.sx(p.UnixTimestamp), py = geo.sy(p.DownloadCount);
    guide.setAttribute("x1", px);
    guide.setAttribute("x2", px);
    guide.style.display = "";
    dot.setAttribute("cx", px);
    dot.setAttribute("cy", py);
    dot.style.display = "";
    tip.innerHTML = `<b>${fmtDate(p.UnixTimestamp)}</b><span>${window.t ? t("meta.downloads", { n: fmtNum(p.DownloadCount) }) : fmtNum(p.DownloadCount) + " 次下载"}</span>`;
    tip.hidden = false;
    const pxScreen = px / k;
    const half = tip.offsetWidth / 2;
    const left = Math.min(Math.max(pxScreen, half + 2), rect.width - half - 2);
    tip.style.left = left + "px";
    tip.style.top = (py / k - 10) + "px";
  };

  svg.addEventListener("pointerdown", (e) => show(e.clientX));
  svg.addEventListener("pointermove", (e) => {
    if (e.pointerType === "mouse" || e.buttons) show(e.clientX);
  });
  svg.addEventListener("pointerup", scheduleHide);
  svg.addEventListener("pointercancel", scheduleHide);
  svg.addEventListener("pointerleave", (e) => {
    if (e.pointerType === "mouse") hide(); else scheduleHide();
  });
}

let trendIO = null;   // 趋势懒加载观察器单例: 导航重建时先断开旧的, 防累积

function initTrend(mod) {
  const section = document.getElementById("trend-section");
  const box = document.getElementById("trend-chart");
  if (!section || !box) return;
  const fallback = () => {
    const link = mod.slug
      ? ` · <a class="link" href="https://outerwildsmods.com/mods/${encodeURIComponent(mod.slug)}/downloads/#downloads" target="_blank" rel="noopener">${window.t ? t("trend.viewOnOfficial") : "在官方站查看"}</a>`
      : "";
    box.innerHTML = `<p class="placeholder">${window.t ? t("trend.failed") : "趋势数据暂时无法获取"}${link}</p>`;
  };
  const noData = () => {
    // 新上传的 MOD 官方统计尚未积累历史(返回空数组/404), 属正常现象
    box.innerHTML = `<p class="placeholder">${window.t ? t("trend.noData") : "该 MOD 暂无趋势数据"}</p>`;
  };
  let started = false;
  const load = async () => {
    if (started) return;
    started = true;
    try {
      const url = `https://outerwildsmods.com/api/${encodeURIComponent(mod.uniqueName)}/downloads.json`;
      const resp = await fetch(url, { mode: "cors" });
      if (resp.status === 404) { noData(); return; }   // 统计服务暂无此 MOD 记录
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const rows = await resp.json();
      if (!Array.isArray(rows) || rows.length < 2) { noData(); return; }   // 历史数据尚未积累
      const chart = trendChartHtml(rows);
      box.innerHTML = chart.html;
      setupTrendInteractions(box, chart.pts, chart.geo);
    } catch (e) {
      fallback();
    }
  };
  if (trendIO) { trendIO.disconnect(); trendIO = null; }
  if ("IntersectionObserver" in window) {
    trendIO = new IntersectionObserver((entries) => {
      if (entries.some((en) => en.isIntersecting)) {
        trendIO.disconnect();
        trendIO = null;
        load();
      }
    }, { rootMargin: "300px 0px" });
    trendIO.observe(section);
  } else {
    load();
  }
}

function renderDetail(mods) {
  const params = new URLSearchParams(location.search);
  const pathHit = location.pathname.match(/\/mod\/([^/]+)\.html$/);
  const uniqueName = pathHit ? decodeURIComponent(pathHit[1]) : params.get("uniqueName");
  const mod = mods.find((m) => m.uniqueName === uniqueName);
  const main = document.getElementById("detail");
  if (!main) return;
  if (!mod) {
    main.innerHTML = `<p class="placeholder">${window.t ? t("detail.notFound") : "未找到该 MOD,"}<a class="link" href="mods.html">${window.t ? t("detail.backList") : "返回列表"}</a></p>`;
    document.title = (window.t ? t("detail.notFoundTitle") : "未找到") + " — " + (window.t ? t("site.name") : "星际拓荒 MOD 数据库");
    return;
  }
  document.title = mod.name + " — " + (window.t ? t("site.name") : "星际拓荒 MOD 数据库");
  const thumb = thumbUrl(mod);
  const repoParts = (mod.repo || "").split("/");
  const reportBody = `MOD: ${mod.name} (${mod.uniqueName})\n页面: ${location.href}\n\n## 问题描述\n\n(哪里的翻译有问题? 原文是什么?)\n\n## 建议译法\n\n(可选)\n`;
  const reportUrl = "https://github.com/dslsdzc/ow-mod-db/issues/new?template=translation.md&title="
    + encodeURIComponent(`[翻译] ${mod.name} (${mod.uniqueName})`)
    + "&body=" + encodeURIComponent(reportBody);
  const repoOwner = repoParts.length >= 2 ? (repoParts[repoParts.length - 2] || "") : "";
  main.innerHTML = `
    <div class="detail">
      ${thumb
        ? `<span class="thumb-box detail-thumb" id="hero-thumb"><img src="${esc(thumb)}" alt="" fetchpriority="high" decoding="async"></span>`
        : `<span class="thumb-box detail-thumb ph-thumb" style="background-image:url('png/21to9.webp')"><span class="ph-text">${esc(mod.name || mod.uniqueName)}</span></span>`}
      <h1>${esc(mod.name)}</h1>
      <div class="meta">${repoOwner ? `<a class="link" href="https://github.com/${esc(repoOwner)}" target="_blank" rel="noopener">@${esc(repoOwner)}</a>` : esc(mod.authorDisplay)} · v${esc(mod.version)} · ${window.t ? t("meta.downloads", { n: mod.downloadCount }) : esc(mod.downloadCount) + " 次下载"} · ${window.t ? t("meta.updatedAt", { d: esc((mod.latestReleaseDate || "").slice(0, 10)) }) : "更新于 " + esc((mod.latestReleaseDate || "").slice(0, 10))}</div>
      <div>${(mod.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      <div class="buttons">
        <a href="owmods://install-mod/${encodeURIComponent(mod.uniqueName)}" title="${window.t ? t("detail.installHint") : "需要已安装 Outer Wilds Mod Manager"}">${window.t ? t("detail.install") : "一键安装"}</a>
        <a class="secondary" href="${esc(mod.downloadUrl)}" target="_blank" rel="noopener">${window.t ? t("detail.downloadZip") : "下载 zip"}${mod.version ? ` (v${esc(mod.version)})` : ""}</a>
      </div>
      <div class="buttons-links">
        ${mod.repo ? `<a href="${esc(mod.repo)}" target="_blank" rel="noopener">${window.t ? t("detail.repoLink") : "源代码仓库"}</a>` : ""}
        <button type="button" id="share-btn">${window.t ? t("detail.share") : "分享"}</button>
        <a href="${reportUrl}" target="_blank" rel="noopener">${window.t ? t("detail.reportIssue") : "报告翻译问题"}</a>
      </div>
      ${mod.description ? `<div class="section"><h3>${window.t ? t("detail.desc") : "简介"}</h3><div class="readme" id="desc-md"></div></div>` : ""}
      ${mod.latestReleaseDescription ? `<div class="section"><h3>${window.t ? t("detail.latestRelease") : "最新版本更新说明"}</h3><div class="readme" id="release-md"></div></div>` : ""}
      <div class="section" id="readme-section" hidden>
        <h3>README</h3>
        <div class="readme-actions" id="readme-actions"></div>
        <div class="readme" id="readme-content"></div>
      </div>
      <div class="section" id="addons-section" hidden>
        <h3>${window.t ? t("detail.addons") : "附属与变体"}</h3>
        <div id="addons-list"></div>
      </div>
      <div class="section" id="releases-section" hidden>
        <div class="section-head">
          <h3>${window.t ? t("detail.releaseHistory") : "版本历史"}</h3>
          <button id="releases-translate-all" class="chip" hidden>${window.t ? t("releases.translateAll") : "全部翻译"}</button>
        </div>
        <div id="releases-list"></div>
      </div>
      <div class="section" id="patch-section" hidden>
        <h3>${window.t ? t("detail.patchSection") : "中文支持"}</h3>
        <div id="patch-box"></div>
      </div>
      <div class="section" id="comments-section" hidden>
        <h3>${window.t ? t("detail.comments") : "讨论区"}</h3>
        <div class="readme-actions"><span class="hint">${window.t ? t("detail.commentsHint") : "评论由 GitHub Discussions 驱动 · 英文评论可用浏览器自带翻译阅读"}</span></div>
        <div id="giscus"></div>
      </div>
      <div class="section" id="trend-section">
        <h3>${window.t ? t("trend.title") : "下载趋势"}</h3>
        <div id="trend-chart"><p class="placeholder">${window.t ? t("trend.loading") : "加载趋势中…"}</p></div>
      </div>
    </div>`;
  const hero = document.getElementById("hero-thumb");
  if (hero) setupThumbBox(hero);
  const descEl = document.getElementById("desc-md");
  if (descEl && mod.description) renderMarkdownInto(descEl, normLines(mod.description), "", true);
  const relEl = document.getElementById("release-md");
  if (relEl && mod.latestReleaseDescription) {
    renderMarkdownInto(relEl, normLines(mod.latestReleaseDescription), "", true);
  }
  initReadme(mod);
  initAddons(mod, mods);
  initReleases(mod);
  initPatchBlock(mod);
  initComments(mod);
  initShare(mod);
  initTrend(mod);
}

function initToTop(signal) {
  const old = document.getElementById("to-top");
  if (old) old.remove();   // Turbo 快照可能带旧按钮: 移除重建, 保证监听绑定到新节点
  const btn = document.createElement("button");
  btn.id = "to-top";
  btn.className = "to-top";
  btn.title = window.t ? t("backTop") : "回到顶部";
  btn.type = "button";
  btn.setAttribute("aria-label", window.t ? t("backTop") : "回到顶部");
  btn.innerHTML =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8l-6 6 1.41 1.41L12 10.83l4.59 4.58L18 14z"/></svg>';
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  btn.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
    btn.blur();
  });
  let ticking = false;
  const update = () => {
    ticking = false;
    btn.classList.toggle("show", window.scrollY > 320);
  };
  window.addEventListener("scroll", () => {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }, { passive: true, signal });
  document.body.appendChild(btn);
}

// ---- 缩略图本地缓存(Service Worker): 回访时图片秒出; 不支持或注册失败则静默跳过 ----
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  });
}

// ---- Turbo 生命周期: 首次加载与每次"无刷新导航"后, 都按当前页面重新初始化 ----
// (turbo:load 首次也会派发, 所以无需另挂 DOMContentLoaded; Turbo 缺失时走兜底)
let bootAbort = null;     // 清理上一页面挂在 window 上的监听
let bootSeq = 0;          // 快速连续导航时放弃过期的初始化
let modsDataCache = null; // 数据跨导航复用, 无刷新切页不再重复拉取

async function boot() {
  const seq = ++bootSeq;
  if (bootAbort) bootAbort.abort();
  bootAbort = new AbortController();
  if (trendIO) { trendIO.disconnect(); trendIO = null; }
  initToTop(bootAbort.signal);
  try {
    if (!modsDataCache) modsDataCache = await loadMods();
    if (seq !== bootSeq) return;             // 期间又发生了新导航: 放弃本次初始化
    const data = modsDataCache;
    const mods = data.mods || [];
    const meta = data.meta || {};
    initSlugMap(mods);
    const syncInfo = document.getElementById("sync-info");
    if (syncInfo && meta.generatedAt) {
      const ts = String(meta.generatedAt).replace("T", " ").slice(0, 16);
      syncInfo.textContent = window.t
        ? t("home.syncInfo", { t: ts, done: meta.zhDescriptions, total: meta.mods })
        : `数据同步于 ${ts} UTC · ${meta.zhDescriptions}/${meta.mods} 个简介已汉化`;
    }
    if (document.getElementById("featured")) renderHome(mods);
    else if (document.getElementById("jams")) renderJams(mods);
    else if (document.getElementById("mod-grid")) renderList(mods);
    else renderDetail(mods);
  } catch (err) {
    const target = document.getElementById("detail")
      || document.getElementById("mod-grid")
      || document.getElementById("featured");
    if (target) target.innerHTML = `<p class="placeholder">${window.t ? t("load.failed") : "加载失败:"}${esc(err.message)}</p>`;
  }
}

document.addEventListener("turbo:load", boot);
document.addEventListener("DOMContentLoaded", () => { if (!window.Turbo) boot(); });   // Turbo 缺席时保持传统加载

// 快照清理: 动态注入的内容不进 Turbo 页面缓存, 避免返回时重复/残留
document.addEventListener("turbo:before-cache", () => {
  const tt = document.getElementById("to-top");
  if (tt) tt.remove();
  const g = document.getElementById("giscus");
  if (g) g.innerHTML = "";
});
