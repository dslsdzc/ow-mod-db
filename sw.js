/* 站点加速 Service Worker —— 所有缓存都只存在【用户浏览器本地】,等同普通浏览缓存,
 * 不做任何再分发。三类策略:
 * 1) 官方缩略图(跨域,官方仅 10 分钟 HTTP 缓存期): cache-first + 7 天后台静默刷新, 回访秒出;
 * 2) 同源静态资源(带版本戳的数据 JSON / js / css, 以及 png/svg 等图片): cache-first, LRU 上限清理;
 * 3) HTML 导航: network-first, 离线/断网时用上次缓存兜底。
 * 升级本文件时请同步 bump 下方缓存版本号(旧桶会在 activate 时清理)。 */
const IMG_CACHE = "ow-thumbs-v2";
const IMG_META = "ow-thumbs-meta-v2";
const ASSET_CACHE = "ow-assets-v2";
const ASSET_META = "ow-assets-meta-v2";
const PAGE_CACHE = "ow-pages-v2";

const THUMB_PREFIX = "https://ow-mods.github.io/ow-mod-db/thumbnails/";
const THUMB_TTL_MS = 7 * 24 * 3600 * 1000;   // 图片本地复用期; 过期后先用旧的、后台刷新
const ASSET_TTL_MS = 30 * 24 * 3600 * 1000;  // 静态资源复用期; 超过视为未缓存(顺带回收旧部署的条目)
const ASSET_MAX = 300;                       // 静态资源条目上限(超出清最久未写入的)
const PAGE_MAX = 100;                        // HTML 缓存条目上限(按写入先后清理)

self.addEventListener("install", () => { self.skipWaiting(); });

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keep = [IMG_CACHE, IMG_META, ASSET_CACHE, ASSET_META, PAGE_CACHE];
    const names = await caches.keys();
    await Promise.all(names
      .filter((n) => n.startsWith("ow-") && !keep.includes(n))
      .map((n) => caches.delete(n)));
    await self.clients.claim();
  })());
});

async function readStamp(meta, url) {
  const r = await meta.match(url);
  return r ? Number(await r.text()) || 0 : 0;
}

/* ---- 1) 官方缩略图: cache-first + 过期后台刷新 ---- */
async function putThumb(cache, meta, url, resp) {
  try {
    await cache.put(url, resp);
    await meta.put(url, new Response(String(Date.now())));
  } catch (e) { /* 缓存失败不影响正常浏览 */ }
}

async function thumbResponse(request) {
  const url = request.url;
  const cache = await caches.open(IMG_CACHE);
  const meta = await caches.open(IMG_META);
  const cached = await cache.match(url);
  if (cached) {
    const at = await readStamp(meta, url);
    if (!at || Date.now() - at > THUMB_TTL_MS) {
      // 已过期: 后台静默更新, 本次仍先用本地副本(秒出)
      fetch(request).then((r) => {
        if (r && (r.ok || r.type === "opaque")) putThumb(cache, meta, url, r);
      }).catch(() => {});
    }
    return cached;
  }
  const resp = await fetch(request);
  if (resp && (resp.ok || resp.type === "opaque")) {
    putThumb(cache, meta, url, resp.clone());  // 先 clone 再返回原响应
  }
  return resp;
}

/* ---- 2) 同源静态资源(数据 JSON / js / css / png 图标): cache-first + LRU 上限 ---- */
async function trimAssets(cache, meta) {
  const keys = await cache.keys();
  if (keys.length <= ASSET_MAX) return;
  const rows = await Promise.all(keys.map(async (req) => ({
    req, at: await readStamp(meta, req.url),
  })));
  rows.sort((a, b) => a.at - b.at);
  for (const row of rows.slice(0, rows.length - ASSET_MAX)) {
    await cache.delete(row.req);
    await meta.delete(row.req.url);
  }
}

async function assetResponse(request) {
  const url = request.url;
  const cache = await caches.open(ASSET_CACHE);
  const meta = await caches.open(ASSET_META);
  const cached = await cache.match(url);
  if (cached) {
    const at = await readStamp(meta, url);
    if (at && Date.now() - at <= ASSET_TTL_MS) return cached;
  }
  const resp = await fetch(request);
  if (resp && resp.ok) {
    try {
      await cache.put(url, resp.clone());
      await meta.put(url, new Response(String(Date.now())));
      await trimAssets(cache, meta);
    } catch (e) { /* 缓存失败不影响正常浏览 */ }
  }
  return resp;
}

/* ---- 3) HTML 导航: network-first(在线永远拿最新; 断网/失败用上次缓存兜底) ---- */
async function pageResponse(request) {
  const cache = await caches.open(PAGE_CACHE);
  try {
    const resp = await fetch(request);
    if (resp && resp.ok) {
      try {
        await cache.put(request, resp.clone());
        const keys = await cache.keys();
        if (keys.length > PAGE_MAX) {
          for (const key of keys.slice(0, keys.length - PAGE_MAX)) await cache.delete(key);
        }
      } catch (e) { /* 缓存失败不影响正常浏览 */ }
    }
    return resp;
  } catch (e) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw e;
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  if (request.url.startsWith(THUMB_PREFIX)) {
    event.respondWith(thumbResponse(request).catch(() => fetch(request)));
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(pageResponse(request));
    return;
  }
  const u = new URL(request.url);
  const sameOrigin = u.origin === self.location.origin;
  const versioned = u.searchParams.has("v");
  const staticImg = /\.(png|svg|ico|webp|jpe?g|gif)$/i.test(u.pathname);
  if (sameOrigin && (versioned || staticImg)) {
    event.respondWith(assetResponse(request).catch(() => fetch(request)));
  }
});
