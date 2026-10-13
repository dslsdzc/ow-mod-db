"""关键路径端到端测试: 首页渲染 / 英文原名搜索 / 详情页导航 / SEO 标签 / SW 缓存与离线兜底。"""

import json
from pathlib import Path

DIST = Path(__file__).resolve().parents[1] / "dist"


def _mods():
    return json.loads((DIST / "data" / "mods.json").read_text(encoding="utf-8"))["mods"]


def _mod_with_translated_name():
    return next(m for m in _mods() if m.get("originalName") and m["originalName"] != m["name"])


def test_home_renders_featured(page, site_server):
    page.goto(site_server + "/index.html")
    page.wait_for_selector("#featured .mod-card")
    assert page.locator("#featured .mod-card").count() == 9  # 三栏 x 3


def test_search_matches_english_original_name(page, site_server):
    mod = _mod_with_translated_name()
    page.goto(site_server + "/mods.html")
    page.wait_for_selector(".mod-card")
    page.fill("#search", mod["originalName"])
    page.wait_for_timeout(500)  # 防抖 120ms + 渲染
    names = page.locator(".mod-card h3").all_text_contents()
    assert mod["name"] in names


def test_card_click_opens_static_detail_page(page, site_server):
    page.goto(site_server + "/mods.html")
    page.wait_for_selector(".mod-card")
    link = page.locator(".mod-card").first
    href = link.get_attribute("href") or ""
    assert href.startswith("mod/") and href.endswith(".html")  # 指向静态详情页
    link.click()
    page.wait_for_selector("#detail h1")
    assert "/mod/" in page.url and page.url.endswith(".html")
    assert "星际拓荒 MOD 数据库" in page.title()


def test_static_detail_page_seo_tags(page, site_server):
    page.goto(site_server + "/mod/xen.NewHorizons.html")
    canonical = page.locator('link[rel="canonical"]').get_attribute("href") or ""
    assert canonical.endswith("/mod/xen.NewHorizons.html")
    og_title = page.locator('meta[property="og:title"]').get_attribute("content") or ""
    assert "新地平线" in og_title
    og_image = page.locator('meta[property="og:image"]').get_attribute("content") or ""
    assert "/og/xen.NewHorizons." in og_image and og_image.endswith(".webp")  # 品牌分享卡片
    fname = og_image.rsplit("/", 1)[1]
    assert page.request.get(site_server + "/og/" + fname).ok                  # 卡片图在构建产物中
    page.wait_for_selector("#detail h1")
    assert page.locator("#share-btn").count() == 1  # 分享按钮渲染


def test_service_worker_registers_and_caches(page, site_server):
    page.goto(site_server + "/mods.html")
    page.wait_for_function("!!navigator.serviceWorker.controller", timeout=20000)
    buckets = page.evaluate("caches.keys()")
    assert any(b.startswith("ow-") for b in buckets)


def test_offline_fallback_after_visit(page, site_server):
    page.goto(site_server + "/mods.html")
    page.wait_for_function("!!navigator.serviceWorker.controller", timeout=20000)
    page.reload()                   # 第二次导航经过 SW, 写入页面缓存(首次导航发生在 SW 接管前)
    page.wait_for_selector(".mod-card")
    page.wait_for_timeout(500)      # 让页面资源写入缓存
    page.context.set_offline(True)
    try:
        page.goto(site_server + "/mods.html")
        page.wait_for_selector(".mod-card", timeout=10000)
    finally:
        page.context.set_offline(False)


def test_seo_files_served(page, site_server):
    sitemap = page.request.get(site_server + "/sitemap.xml")
    assert sitemap.ok and "urlset" in sitemap.text()
    robots = page.request.get(site_server + "/robots.txt")
    assert robots.ok and "Sitemap:" in robots.text()
