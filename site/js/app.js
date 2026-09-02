async function loadMods() {
  const resp = await fetch("data/mods.json");
  if (!resp.ok) throw new Error("无法加载数据: " + resp.status);
  return resp.json();
}

function esc(s) {
  const div = document.createElement("div");
  div.textContent = String(s == null ? "" : s);
  return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function thumbUrl(m) {
  return m.thumbnail && m.thumbnail.main
    ? "https://ow-mods.github.io/ow-mod-db/thumbnails/" + m.thumbnail.main
    : "";
}

function cardHtml(m) {
  const thumb = thumbUrl(m);
  return `<a class="mod-card" href="mod.html?uniqueName=${encodeURIComponent(m.uniqueName)}">
    ${thumb ? `<img class="thumb" src="${esc(thumb)}" alt="" loading="lazy">` : ""}
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
  if (mode === "popularNew") {
    const cutoff = Date.now() - 60 * 24 * 3600 * 1000;
    const recent = copy.filter((m) => m.firstReleaseDate && new Date(m.firstReleaseDate).getTime() >= cutoff);
    return recent.sort((a, b) => installs(b) - installs(a));
  }
  return copy;
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
}

function renderList(mods) {
  const grid = document.getElementById("mod-grid");
  const search = document.getElementById("search");
  const tagFilter = document.getElementById("tag-filter");
  const count = document.getElementById("count");
  if (!grid) return;

  const allTags = [...new Set(mods.flatMap((m) => m.tags || []))].sort();
  for (const tag of allTags) {
    const opt = document.createElement("option");
    opt.value = tag;
    opt.textContent = tag;
    tagFilter.appendChild(opt);
  }

  function draw() {
    const q = search.value.trim().toLowerCase();
    const tag = tagFilter.value;
    const shown = mods.filter((m) => {
      if (tag && !(m.tags || []).includes(tag)) return false;
      if (!q) return true;
      return (m.name + " " + m.description + " " + m.authorDisplay).toLowerCase().includes(q);
    });
    count.textContent = shown.length + " / " + mods.length + " 个 MOD";
    grid.innerHTML = shown.map(cardHtml).join("") || `<p class="placeholder">没有匹配的 MOD</p>`;
  }

  search.addEventListener("input", draw);
  tagFilter.addEventListener("change", draw);
  draw();
}

async function fetchJson(url) {
  const resp = await fetch(url);
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

function splitChunks(text, maxChars) {
  const parts = text.split(/\n{2,}/);
  const chunks = [];
  let cur = "";
  for (const p of parts) {
    const piece = p.trim();
    if (!piece) continue;
    if (piece.length > maxChars) {
      for (let i = 0; i < piece.length; i += maxChars) chunks.push(piece.slice(i, i + maxChars));
      continue;
    }
    const cand = cur ? cur + "\n\n" + piece : piece;
    if (cand.length > maxChars) { chunks.push(cur); cur = piece; }
    else cur = cand;
  }
  if (cur) chunks.push(cur);
  return chunks;
}

function renderMarkdownInto(el, md, baseUrl) {
  if (!window.marked || !window.DOMPurify) {
    el.innerHTML = `<p class="placeholder">渲染库未加载(CDN 不可达),<a class="link" href="${esc(baseUrl)}" target="_blank" rel="noopener">打开仓库原文目录</a></p>`;
    return;
  }
  const raw = marked.parse(md, { gfm: true, breaks: false });
  el.innerHTML = DOMPurify.sanitize(raw);
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
  script.setAttribute("data-term", mod.uniqueName);   // 每个 mod 独立讨论串
  script.setAttribute("data-strict", "0");
  script.setAttribute("data-reactions-enabled", "1");
  script.setAttribute("data-emit-metadata", "0");
  script.setAttribute("data-input-position", "top");
  script.setAttribute("data-theme", "dark");
  script.setAttribute("data-lang", "zh-CN");
  script.setAttribute("crossorigin", "anonymous");
  script.async = true;
  document.getElementById("giscus").appendChild(script);
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
        const btn = document.createElement("button");
        btn.textContent = "查看英文原文";
        btn.onclick = async () => {
          try { showMd(await fetchEn()); setHint("英文原文 · 原文版权归作者所有"); }
          catch (e) { setHint("加载失败:" + e.message); }
        };
        actions.prepend(btn);
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
            const chunks = splitChunks(md, 1200);
            const out = [];
            for (const c of chunks) out.push(await msTranslateTexts([c]));
            showMd(out.join("\n\n"));
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
  main.innerHTML = `
    <div class="detail">
      ${thumb ? `<img class="thumb" src="${esc(thumb)}" alt="">` : ""}
      <h1>${esc(mod.name)}</h1>
      <div class="meta">${esc(mod.authorDisplay)} · v${esc(mod.version)} · ${esc(mod.downloadCount)} 次下载 · 更新于 ${esc((mod.latestReleaseDate || "").slice(0, 10))}</div>
      <div>${(mod.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      <div class="buttons">
        <a href="${esc(mod.downloadUrl)}" target="_blank" rel="noopener">下载 MOD</a>
        ${mod.repo ? `<a class="secondary" href="${esc(mod.repo)}" target="_blank" rel="noopener">源代码仓库</a>` : ""}
      </div>
      ${mod.description ? `<div class="section"><h3>简介</h3><p>${esc(mod.description)}</p></div>` : ""}
      ${mod.latestReleaseDescription ? `<div class="section"><h3>最新版本更新说明</h3><p>${esc(mod.latestReleaseDescription)}</p></div>` : ""}
      <div class="section" id="readme-section" hidden>
        <h3>README</h3>
        <div class="readme-actions" id="readme-actions"></div>
        <div class="readme" id="readme-content"></div>
      </div>
      <div class="section" id="comments-section" hidden>
        <h3>讨论区</h3>
        <div class="readme-actions"><span class="hint">评论由 GitHub Discussions 驱动 · 英文评论可用浏览器自带翻译阅读</span></div>
        <div id="giscus"></div>
      </div>
    </div>`;
  initReadme(mod);
  initComments(mod);
}

loadMods()
  .then((data) => {
    const mods = data.mods || [];
    const meta = data.meta || {};
    const syncInfo = document.getElementById("sync-info");
    if (syncInfo && meta.generatedAt) {
      const t = String(meta.generatedAt).replace("T", " ").slice(0, 16);
      syncInfo.textContent = `数据同步于 ${t} UTC · ${meta.zhDescriptions}/${meta.mods} 个简介已汉化`;
    }
    if (document.getElementById("featured")) renderHome(mods);
    else if (document.getElementById("mod-grid")) renderList(mods);
    else renderDetail(mods);
  })
  .catch((err) => {
    const target = document.getElementById("detail")
      || document.getElementById("mod-grid")
      || document.getElementById("featured");
    if (target) target.innerHTML = `<p class="placeholder">加载失败:${esc(err.message)}</p>`;
  });
