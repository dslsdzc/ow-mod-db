function withV(url) {
  const v = window.DATA_V || "";
  return v ? url + (url.includes("?") ? "&" : "?") + "v=" + v : url;
}

async function loadMods() {
  const resp = await fetch(withV("data/mods.json"));
  if (!resp.ok) throw new Error("无法加载数据: " + resp.status);
  return resp.json();
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

const THUMB_BG = { "1/1": "png/1to1.png", "16/9": "png/16to9.png", "21/9": "png/21to9.png" };

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

function cardHtml(m) {
  const thumb = thumbUrl(m);
  const visual = thumb
    ? `<span class="thumb-box"><img src="${esc(thumb)}" alt="" loading="lazy"></span>`
    : `<span class="thumb-box ph-thumb" style="background-image:url('png/16to9.png')"><span class="ph-text">${esc(m.name || m.uniqueName || "?")}</span></span>`;
  return `<a class="mod-card" href="mod.html?uniqueName=${encodeURIComponent(m.uniqueName)}">
    ${visual}
    <h3>${esc(m.name)}</h3>
    <div class="meta">${esc(m.authorDisplay)} · v${esc(m.version)} · ${esc(m.downloadCount)} 次下载</div>
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
    fetchJson("data/jams.json").catch(() => ({})),
    fetchJson("data/jam_content.json").catch(() => ({})),
  ]).then(([cfg, content]) => {
    cfg = cfg || {};
    content = content || {};
    const overrides = cfg.overrides || {};
    const buckets = new Map();
    for (const m of mods) {
      const k = jamKey(m);
      if (!k) continue;
      if (!buckets.has(k)) buckets.set(k, []);
      buckets.get(k).push(m);
    }
    const entries = [...buckets.entries()]
      .sort((a, b) => (parseInt(b[0].replace("jam", "")) || 0) - (parseInt(a[0].replace("jam", "")) || 0));
    if (!entries.length) {
      root.innerHTML = `<p class="placeholder">暂未识别到 Jam 参赛 mod</p>`;
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
      if (k === "other") return (cfg.fallbackTitle || "其他 Jam 作品");
      return "历届 Jam 届次(待补充)";   // 不做数字编号,保持可扩展
    };
    root.innerHTML = entries.map(([k, list]) => {
      list.sort((a, b) => installs(b) - installs(a));
      const o = overrides[k] || {};
      const c = content[k] || {};
      const sections = (c.sections || []).map((s, i) =>
        `<div class="jam-sec"><h3>${esc(s.h)}</h3><div class="readme jam-md-${k}-${i}"></div></div>`).join("");
      return `<section class="home-section" data-jam="${esc(k)}">
        <h2>${esc(titleOf(k))} <span class="meta">· ${list.length} 个作品</span></h2>
        ${c.introZh ? `<div class="readme" data-bucket-md="${esc(k)}"></div>` : ""}
        ${(c.officialUrl || o.officialUrl) ? `<p><a class="link" href="${esc(c.officialUrl || o.officialUrl)}" target="_blank" rel="noopener">官方届次页面</a></p>` : ""}
        ${sections}
        ${c.sections && c.sections.length ? `<p class="foot-note">译文依据官方 Jam 页面撰写,版权归主办方;参赛作品列表为本站自动聚合。</p>` : ""}
        <div class="grid">${list.map(cardHtml).join("")}</div>
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
        if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      root.prepend(nav);
    }
    setupAllThumbs(root);
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
      if (sec && sec.md) renderMarkdownInto(el, sec.md, "", false);
    });
    // 独立信息页(如 2026 Game Jam,无本地参赛分组)
    const pagesHtml = Object.entries(content.pages || {}).map(([pk, p]) => `
      <section class="home-section jam-sec" data-page="${esc(pk)}">
        <h2>${esc(p.titleZh || "")}</h2>
        <div class="readme" data-page-md></div>
        <div class="cta-row" style="margin-top:.6rem;">
          <a class="cta" href="${esc(p.url || "#")}" target="_blank" rel="noopener">${esc(p.urlLabelZh || "前往官方页面")}</a>
        </div>
        ${(p.sections || []).map((s, i) => `<div class="jam-sec"><h3>${esc(s.h)}</h3><div class="readme" data-page-sec="${pk}-${i}"></div></div>`).join("")}
        <p class="foot-note">译文依据官方 Jam 页面撰写,版权归主办方。</p>
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
        if (box && s.md) renderMarkdownInto(box, s.md, "", false);
      });
    });
  }).catch((err) => {
    root.innerHTML = `<p class="placeholder">Jam 页渲染失败:${esc(err && err.message ? err.message : String(err))}</p>`;
  });
  } catch (e) {
    root.innerHTML = `<p class="placeholder">Jam 页渲染失败:${esc(e && e.message ? e.message : String(e))}</p>`;
  }
}

function renderHome(mods) {
  const total = document.getElementById("mod-total");
  if (total) total.textContent = `目前共有 ${mods.length} 个 MOD、扩展与工具。`;
  const featured = document.getElementById("featured");
  if (!featured) return;
  const sections = [
    ["热门 MOD", "installs"],
    ["热门新 MOD", "popularNew"],
    ["最近更新", "updated"],
  ];
  featured.innerHTML = sections.map(([title, mode]) => {
    const items = sortMods(mods, mode).slice(0, 3);
    return `<section><h2>${title}</h2><div class="grid">${items.map(cardHtml).join("")}</div></section>`;
  }).join("");
  setupAllThumbs(featured);
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
    mk("全部", "");
    for (const t of allTags) mk(t, t);
  }
  function refreshChips() {
    if (!chipsEl) return;
    [...chipsEl.children].forEach((b) => b.classList.toggle("active", b.dataset.tag === tag));
  }

  function draw() {
    const q = search.value.trim().toLowerCase();
    const mode = sort ? sort.value : "installs";
    let shown = mods.filter((m) => {
      if (tag && !(m.tags || []).includes(tag)) return false;
      if (!q) return true;
      return (m.name + " " + m.description + " " + m.authorDisplay).toLowerCase().includes(q);
    });
    shown = sortMods(shown, mode);
    count.textContent = shown.length + " / " + mods.length + " 个 MOD";
    grid.innerHTML = shown.map(cardHtml).join("") || `<p class="placeholder">没有匹配的 MOD</p>`;
    setupAllThumbs(grid);
  }

  search.addEventListener("input", draw);
  if (sort) sort.addEventListener("change", draw);
  draw();
}

async function fetchJson(url) {
  const resp = await fetch(withV(url));
  if (!resp.ok) throw new Error(url + " " + resp.status);
  return resp.json();
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

function renderMermaidBlocks(scope) {
  if (!window.mermaid) return;
  const blocks = [...(scope || document).querySelectorAll("pre > code.language-mermaid")];
  if (!blocks.length) return;
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
      a.href = "mod.html?uniqueName=" + encodeURIComponent(uid);
      a.removeAttribute("target");
    }
  });
}

function renderMarkdownInto(el, md, baseUrl, breaks) {
  if (!window.marked || !window.DOMPurify) {
    el.innerHTML = `<p class="placeholder">渲染库未加载(CDN 不可达),<a class="link" href="${esc(baseUrl)}" target="_blank" rel="noopener">打开仓库原文目录</a></p>`;
    return;
  }
  const raw = marked.parse(md, { gfm: true, breaks: !!breaks });
  el.innerHTML = DOMPurify.sanitize(raw);
  renderMermaidBlocks(el);
  // 加载失败的图(如徽章图无法访问)直接隐藏,不显示 alt 文本噪音
  el.querySelectorAll("img").forEach((img) => {
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
        `<div><p style="margin:0 0 .4rem;">${esc(p.name || "中文支持")}</p>
         <div class="cta-row">${installBtn}</div>
         ${p.note ? `<p class="foot-note">${esc(p.note)}</p>` : ""}
         ${manualNote}
         <p class="foot-note">补丁为社区作品,版权归作者所有。</p></div>`;
    })
    .catch(() => section.remove());
}

function initReleases(mod) {
  const section = document.getElementById("releases-section");
  const list = document.getElementById("releases-list");
  if (!section || !list) return;
  fetchJson("data/releases/" + encodeURIComponent(mod.uniqueName) + ".json")
    .then((data) => {
      const rels = (data && data.releases) || [];
      if (!rels.length) { section.remove(); return; }
      section.hidden = false;
      const SHOW = 5;

      function renderItems(items) {
        const itemHtml = (r) => `<div class="rel-item">
          <div class="rel-head">
            <a class="rel-tag" href="${esc(r.zipUrl || r.releaseUrl || "#")}" target="_blank" rel="noopener">${esc(r.tag)}</a>
            <span class="rel-meta">${esc(r.name !== r.tag ? r.name : "")} · ${esc(r.date)}</span>
            ${r.zipUrl ? `<a class="rel-zip" href="${esc(r.zipUrl)}" target="_blank" rel="noopener">zip</a>` : ""}
            ${r.body ? `<button class="chip rel-tr">${r.bodyZh ? "原文" : "微软翻译"}</button>` : ""}
          </div>
          ${r.body ? `<div class="readme rel-body"></div>` : ""}
        </div>`;
        list.innerHTML = items.map(itemHtml).join("");
        [...list.querySelectorAll(".rel-item")].forEach((el, i) => {
          const r = items[i];
          const bodyEl = el.querySelector(".rel-body");
          const btn = el.querySelector(".rel-tr");
          if (!r || !r.body) return;
          renderMarkdownInto(bodyEl, r.bodyZh || r.body, "");
          if (btn) {
            btn.onclick = async () => {
              if (btn.classList.contains("busy")) return;
              if (btn.textContent === "原文") {
                renderMarkdownInto(bodyEl, r.body, "");
                btn.textContent = r.bodyZh ? "中文译文" : "微软翻译";
                return;
              }
              btn.classList.add("busy");
              btn.textContent = "翻译中…";
              try {
                const zh = await msTranslateTexts([r.body]);
                renderMarkdownInto(bodyEl, zh[0] || r.body, "");
                btn.textContent = "原文";
              } catch (e) {
                btn.textContent = "翻译失败";
              } finally {
                btn.classList.remove("busy");
              }
            };
          }
        });
      }

      const more = rels.length > SHOW;
      renderItems(more ? rels.slice(0, SHOW) : rels);
      if (more) {
        const btn = document.createElement("button");
        btn.className = "chip";
        btn.textContent = `显示全部 ${rels.length} 个版本`;
        btn.onclick = () => { renderItems(rels); btn.remove(); };
        list.appendChild(btn);
      }
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
      ? "mod.html?uniqueName=" + encodeURIComponent(m.uniqueName)
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
  const setHint = (text) => { actions.innerHTML = `<span class="hint">${esc(text)}</span>`; };
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
        fetchJson("data/readmes.json").catch(() => ({})),
        fetchJson("data/licenses.json").catch(() => ({})),
      ]);
      const zh = readmes[mod.uniqueName];
      const lic = licenses[mod.uniqueName] || "";
      const permissive = ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
                          "Unlicense", "0BSD", "MIT-0", "MPL-2.0"].includes(lic);

      if (zh && zh.zh) {
        setHint("译文由 AI 生成 · 原文版权归作者所有 · " + lic);
        showMd(zh.zh);
        // 两个显式按钮互相切换(比单按钮改文字更可靠,无状态残留)
        const zhBtn = document.createElement("button");
        zhBtn.textContent = "回到中文译文";
        zhBtn.hidden = true;
        const enBtn = document.createElement("button");
        enBtn.textContent = "查看英文原文";
        const setActive = (zhActive) => {
          zhBtn.hidden = !zhActive;
          enBtn.hidden = zhActive;
        };
        zhBtn.onclick = () => {
          showMd(zh.zh);
          setHint("译文由 AI 生成 · 原文版权归作者所有 · " + lic);
          setActive(true);
        };
        enBtn.onclick = async () => {
          if (enBtn.classList.contains("busy")) return;
          enBtn.classList.add("busy");
          try {
            showMd(await fetchEn());
            setHint("英文原文 · 原文版权归作者所有");
            setActive(false);
          } catch (e) { setHint("加载失败:" + e.message); }
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
        btn.textContent = "微软翻译查看";
        btn.onclick = async () => {
          btn.classList.add("busy");
          btn.textContent = "翻译中…";
          try {
            // 先渲染英文 HTML(链接/图片/代码块保持原样),再只翻译可见文本
            showMd(md);
            await translateReadmeDom(content);
            setHint("微软翻译即时结果 · " + hintBase);
          } catch (e) {
            setHint("翻译失败:" + e.message + " (可换用浏览器自带翻译)");
          } finally {
            btn.classList.remove("busy");
            btn.textContent = "微软翻译查看";
          }
        };
        actions.prepend(btn);
      };
      if (permissive) {
        setHint(lic + " 许可 · 译文生成中,可用「微软翻译查看」即时浏览(不保存)");
        showMd(md);
        addMsButton("仅本次查看,不保存");
      } else {
        // 非开放许可(AGPL/GPL/无): 尊重版权不预翻不保存;
        // 但用户即时浏览性翻译等同于浏览器翻译,仍提供按钮
        setHint("仓库许可为 " + (lic === "none" ? "未声明(保留所有权利)" : lic)
                + ",未保存译文;下方按钮为即时翻译,仅供本次阅读、不保存");
        showMd(md);
        addMsButton("原文版权归作者所有 · 仅本次阅读,不保存");
      }
    } catch (e) {
      setHint("README 加载失败:" + e.message);
    }
  })();
}

function renderDetail(mods) {
  const params = new URLSearchParams(location.search);
  const uniqueName = params.get("uniqueName");
  const mod = mods.find((m) => m.uniqueName === uniqueName);
  const main = document.getElementById("detail");
  if (!main) return;
  if (!mod) {
    main.innerHTML = `<p class="placeholder">未找到该 MOD,<a class="link" href="mods.html">返回列表</a></p>`;
    document.title = "未找到 — 星际拓荒 MOD 数据库";
    return;
  }
  document.title = mod.name + " — 星际拓荒 MOD 数据库";
  const thumb = thumbUrl(mod);
  const repoParts = (mod.repo || "").split("/");
  const repoOwner = repoParts.length >= 2 ? (repoParts[repoParts.length - 2] || "") : "";
  main.innerHTML = `
    <div class="detail">
      ${thumb
        ? `<span class="thumb-box detail-thumb" id="hero-thumb"><img src="${esc(thumb)}" alt=""></span>`
        : `<span class="thumb-box detail-thumb ph-thumb" style="background-image:url('png/21to9.png')"><span class="ph-text">${esc(mod.name || mod.uniqueName)}</span></span>`}
      <h1>${esc(mod.name)}</h1>
      <div class="meta">${repoOwner ? `<a class="link" href="https://github.com/${esc(repoOwner)}" target="_blank" rel="noopener">@${esc(repoOwner)}</a>` : esc(mod.authorDisplay)} · v${esc(mod.version)} · ${esc(mod.downloadCount)} 次下载 · 更新于 ${esc((mod.latestReleaseDate || "").slice(0, 10))}</div>
      <div>${(mod.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      <div class="buttons">
        <a href="owmods://install-mod/${encodeURIComponent(mod.uniqueName)}" title="需要已安装 Outer Wilds Mod Manager">一键安装</a>
        <a class="secondary" href="${esc(mod.downloadUrl)}" target="_blank" rel="noopener">下载 zip${mod.version ? ` (v${esc(mod.version)})` : ""}</a>
        ${mod.repo ? `<a class="secondary" href="${esc(mod.repo)}" target="_blank" rel="noopener">源代码仓库</a>` : ""}
      </div>
      ${mod.slug ? `<div class="buttons-second">
        <a class="secondary" href="https://outerwildsmods.com/mods/${encodeURIComponent(mod.slug)}/downloads/#downloads" target="_blank" rel="noopener">下载统计</a>
      </div>` : ""}
      ${mod.description ? `<div class="section"><h3>简介</h3><div class="readme" id="desc-md"></div></div>` : ""}
      ${mod.latestReleaseDescription ? `<div class="section"><h3>最新版本更新说明</h3><div class="readme" id="release-md"></div></div>` : ""}
      <div class="section" id="readme-section" hidden>
        <h3>README</h3>
        <div class="readme-actions" id="readme-actions"></div>
        <div class="readme" id="readme-content"></div>
      </div>
      <div class="section" id="addons-section" hidden>
        <h3>附属与变体</h3>
        <div id="addons-list"></div>
      </div>
      <div class="section" id="releases-section" hidden>
        <h3>版本历史</h3>
        <div id="releases-list"></div>
      </div>
      <div class="section" id="patch-section" hidden>
        <h3>中文支持</h3>
        <div id="patch-box"></div>
      </div>
      <div class="section" id="comments-section" hidden>
        <h3>讨论区</h3>
        <div class="readme-actions"><span class="hint">评论由 GitHub Discussions 驱动 · 英文评论可用浏览器自带翻译阅读</span></div>
        <div id="giscus"></div>
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
}

(function initToTop() {
  if (document.getElementById("to-top")) return;
  const btn = document.createElement("button");
  btn.id = "to-top";
  btn.className = "to-top";
  btn.title = "回到顶部";
  btn.type = "button";
  btn.setAttribute("aria-label", "回到顶部");
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
  }, { passive: true });
  document.body.appendChild(btn);
})();

loadMods()
  .then((data) => {
    const mods = data.mods || [];
    const meta = data.meta || {};
    initSlugMap(mods);
    const syncInfo = document.getElementById("sync-info");
    if (syncInfo && meta.generatedAt) {
      const t = String(meta.generatedAt).replace("T", " ").slice(0, 16);
      syncInfo.textContent = `数据同步于 ${t} UTC · ${meta.zhDescriptions}/${meta.mods} 个简介已汉化`;
    }
    if (document.getElementById("featured")) renderHome(mods);
    else if (document.getElementById("jams")) renderJams(mods);
    else if (document.getElementById("mod-grid")) renderList(mods);
    else renderDetail(mods);
  })
  .catch((err) => {
    const target = document.getElementById("detail")
      || document.getElementById("mod-grid")
      || document.getElementById("featured");
    if (target) target.innerHTML = `<p class="placeholder">加载失败:${esc(err.message)}</p>`;
  });
