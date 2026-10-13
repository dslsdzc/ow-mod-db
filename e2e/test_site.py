"""关键路径端到端测试: 首页渲染 / 英文原名搜索 / 详情页导航 / SEO 标签 / SW 缓存与离线兜底。"""

import json
import re
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


def test_ja_mode_has_no_chinese_ui_leaks(page, site_server):
    """日语界面上不应残留未 i18n 的中文界面文案(运行时全面扫描)。"""
    page.context.add_init_script("localStorage.setItem('ui-lang','ja')")
    leaks = ["目前共有", "交流与反馈", "成为汉化贡献者", "返回列表", "源代码仓库", "一键安装",
             "下载 zip", "版本历史", "讨论区", "最新版本更新说明", "附属与变体",
             "没有匹配的 MOD", "页面不存在", "加载失败",
             "jams.title", "jams.works", "jams.placeholder", "manager.title"]
    for path in ("/index.html", "/mods.html", "/mod-manager.html", "/404.html",
                 "/jams.html", "/mod/xen.NewHorizons.html"):
        page.goto(site_server + path)
        page.wait_for_timeout(700)
        body = page.locator("body").inner_text()
        for w in leaks:
            assert w not in body, f"{path} 出现中文界面残留: {w}"


def test_detail_trend_falls_back_without_official_api(page, site_server):
    """官方统计 API 不可达时, 趋势区块优雅降级为提示+外链(不报错)。"""
    page.route(re.compile(r"outerwildsmods\.com"), lambda route: route.abort())
    page.goto(site_server + "/mod/xen.NewHorizons.html")
    page.wait_for_selector("#detail h1")
    page.locator("#trend-section").scroll_into_view_if_needed()
    page.wait_for_timeout(1000)
    text = page.locator("#trend-chart").inner_text()
    assert "趋势" in text                                   # zh 降级文案
    assert page.locator("#trend-section a.link").count() == 1  # 官方站查看链接


def test_detail_trend_shows_no_data_state(page, site_server):
    """官方统计返回空数组(新 MOD)时显示"暂无趋势数据"而不是"无法获取"。"""
    page.route(re.compile(r"outerwildsmods\.com"), lambda route: route.fulfill(
        status=200, content_type="application/json", body="[]"))
    page.goto(site_server + "/mod/Hamstry.TheLongerTheyLoad.html")
    page.wait_for_selector("#detail h1")
    page.locator("#trend-section").scroll_into_view_if_needed()
    page.wait_for_timeout(1000)
    text = page.locator("#trend-chart").inner_text()
    assert "暂无趋势数据" in text
    assert "无法获取" not in text


def test_detail_readme_toggle_between_translation_and_original(page, site_server):
    """README 译文/原文切换: 点"查看英文原文"后必须仍有"回到译文"按钮(防回归)。"""
    page.route(re.compile(r"raw\.githubusercontent\.com"), lambda route: route.fulfill(
        status=200, content_type="text/plain", body="# Hello Original"))
    page.goto(site_server + "/mod/xen.NewHorizons.html")
    page.wait_for_selector("#detail h1")
    page.locator("#readme-section").scroll_into_view_if_needed()
    page.get_by_role("button", name=re.compile("查看英文原文")).wait_for(timeout=10000)   # 预翻译路径的按钮
    page.get_by_role("button", name=re.compile("查看英文原文")).click()
    page.wait_for_timeout(600)
    back = page.get_by_role("button", name=re.compile("回到中文译文"))
    assert back.is_visible()                       # bug 场景: 此按钮曾被销毁
    assert "Hello Original" in page.locator("#readme-content").inner_text()
    back.click()
    page.wait_for_timeout(300)
    assert "Hello Original" not in page.locator("#readme-content").inner_text()


def test_seo_files_served(page, site_server):
    sitemap = page.request.get(site_server + "/sitemap.xml")
    assert sitemap.ok and "urlset" in sitemap.text()
    robots = page.request.get(site_server + "/robots.txt")
    assert robots.ok and "Sitemap:" in robots.text()
