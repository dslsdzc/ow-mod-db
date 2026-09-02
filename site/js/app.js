async function loadMods() {
  const resp = await fetch("data/mods.json");
  if (!resp.ok) throw new Error("无法加载数据: " + resp.status);
  return (await resp.json()).mods;
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
    </div>`;
}

loadMods()
  .then((mods) => {
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
