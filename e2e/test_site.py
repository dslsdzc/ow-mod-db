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


def _install_ms_mock(page, text="测试译文", counter=None):
    """拦截微软 Edge 翻译端点, 按请求条数回等长译文(离线确定性测试)。

    counter: 传入 list 时, 每次请求追加 URL(用于断言"不该发请求"的场景)。
    """
    import json as _json

    def handler(route):
        if counter is not None:
            counter.append(route.request.url)
        texts = _json.loads(route.request.post_data or "[]")
        body = _json.dumps([{"translations": [{"text": text}]} for _ in texts],
                           ensure_ascii=False)
        route.fulfill(status=200, content_type="application/json", body=body)

    page.route(re.compile(r"edge\.microsoft\.com"), handler)


def test_readme_ms_translate_button_toggles_between_translation_and_original(page, site_server):
    """README 翻译按钮: 翻译完成后应变为"查看英文原文", 再点切回原文(而非重复翻译)。"""
    _install_ms_mock(page)
    page.goto(site_server + "/mod/Tlya.OnlyTH.html")
    page.wait_for_selector("#detail h1")
    page.locator("#readme-section").scroll_into_view_if_needed()
    ms_btn = page.locator("#readme-actions button", has_text="翻译")
    ms_btn.wait_for(timeout=10000)
    assert ms_btn.inner_text().strip() == "翻译"                 # 按钮文案仅"翻译"两字
    ms_btn.click()
    back = page.locator("#readme-actions button", has_text="查看英文原文")
    back.wait_for(timeout=15000)                                 # 翻译后按钮切换为"查看英文原文"
    back.click()
    page.locator("#readme-actions button", has_text="翻译").wait_for(timeout=5000)
    assert "测试译文" not in page.locator("#readme-content").inner_text()


def test_releases_translate_all_bulk_translates_and_hides(page, site_server):
    """版本历史"全部翻译": 一键翻译所有待翻版本, 完成后按钮隐藏、各版本可切回原文。"""
    _install_ms_mock(page)
    page.goto(site_server + "/mod/Tlya.OnlyTH.html")
    page.wait_for_selector("#detail h1")
    page.locator("#releases-section").scroll_into_view_if_needed()
    all_btn = page.locator("#releases-translate-all")
    all_btn.wait_for(state="visible", timeout=10000)
    assert page.locator("#releases-section .rel-tr").first.inner_text().strip() == "翻译"
    all_btn.click()
    all_btn.wait_for(state="hidden", timeout=15000)              # 全部翻完 → 按钮隐藏
    assert "测试译文" in page.locator("#releases-section .rel-body").first.inner_text()
    for btn in page.locator("#releases-section .rel-tr").all():
        assert btn.inner_text().strip() == "原文"                # 各版本按钮切为"原文"


def test_seo_files_served(page, site_server):
    sitemap = page.request.get(site_server + "/sitemap.xml")
    assert sitemap.ok and "urlset" in sitemap.text()
    robots = page.request.get(site_server + "/robots.txt")
    assert robots.ok and "Sitemap:" in robots.text()


def test_list_search_filter_empty_and_clear(page, site_server):
    """列表页搜索闭环: 中文词过滤→无结果空状态→清空恢复全量。"""
    page.goto(site_server + "/mods.html")
    page.wait_for_selector(".mod-card")
    n0 = page.locator(".mod-card").count()
    assert n0 > 50
    page.fill("#search", "新视野")
    page.wait_for_timeout(700)
    n1 = page.locator(".mod-card").count()
    assert 0 < n1 < n0 and "新视野" in page.locator(".mod-card").first.inner_text()
    page.fill("#search", "zzzqqq不存在")
    page.wait_for_timeout(700)
    assert page.locator(".mod-card").count() == 0
    assert "没有匹配" in page.locator("main").inner_text()
    page.fill("#search", "")
    page.wait_for_timeout(700)
    assert page.locator(".mod-card").count() == n0


def test_list_sort_switches_reorder(page, site_server):
    """排序四选项逐一切换: 卡片数不变, 不同排序给出不同首卡(排序真实生效)。"""
    page.goto(site_server + "/mods.html")
    page.wait_for_selector(".mod-card")
    n0 = page.locator(".mod-card").count()
    firsts = set()
    for value in ("newest", "updated", "name", "installs"):
        page.select_option("#sort", value)
        page.wait_for_timeout(400)
        assert page.locator(".mod-card").count() == n0
        firsts.add(page.locator(".mod-card h3").first.inner_text())
    assert len(firsts) >= 3


def test_list_tag_chip_toggle(page, site_server):
    """标签筛选: 点击筛选→再点取消→计数恢复。"""
    page.goto(site_server + "/mods.html")
    page.wait_for_selector(".mod-card")
    n0 = page.locator(".mod-card").count()
    page.click("#tag-chips .chip[data-tag='gameplay']")
    page.wait_for_timeout(500)
    ng = page.locator(".mod-card").count()
    assert 0 < ng < n0
    assert page.locator("#tag-chips .chip.active").inner_text().strip() == "gameplay"
    page.click("#tag-chips .chip[data-tag='gameplay']")
    page.wait_for_timeout(500)
    assert page.locator(".mod-card").count() == n0


def test_lang_switch_roundtrip(page, site_server):
    """界面语言切换 zh→ja→zh 往返(切换器 reload 后文案正确)。"""
    page.goto(site_server + "/mods.html")
    page.wait_for_selector(".mod-card")
    vals = page.locator(".lang-switch option").evaluate_all("o => o.map(x => x.value)")
    ja = [v for v in vals if v != "zh-CN"][0]
    page.select_option(".lang-switch", ja)
    page.wait_for_selector(".mod-card")
    page.wait_for_timeout(300)
    assert page.locator("main h1").inner_text() == "すべてのMOD"
    page.select_option(".lang-switch", "zh-CN")
    page.wait_for_selector(".mod-card")
    page.wait_for_timeout(300)
    assert page.locator("main h1").inner_text() == "全部 MOD"


def test_releases_zh_toggle_roundtrip(page, site_server):
    """版本历史按钮状态机闭环:
    有预翻译版本 原文↔译文 往返全程 0 次机翻请求;
    无预翻译版本 机翻 1 次后, 往返复用缓存不重复请求(回归: 曾误走机翻)。"""
    import json as _json

    rels = {"releases": [
        {"tag": "1.0.0", "name": "1.0.0", "date": "2026-01-01",
         "body": "Fixed stuff", "bodyZh": "修复了东西"},
        {"tag": "0.9.0", "name": "0.9.0", "date": "2025-12-01",
         "body": "Initial release", "bodyZh": ""},
    ]}
    ms_calls = []
    page.route("**/releases/xen.NewHorizons.json*", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=_json.dumps(rels, ensure_ascii=False)))
    _install_ms_mock(page, text="机翻结果", counter=ms_calls)
    page.goto(site_server + "/mod/xen.NewHorizons.html")
    page.wait_for_selector("#detail h1")
    page.locator("#releases-section").scroll_into_view_if_needed()
    page.locator("#releases-section .rel-tr").first.wait_for(timeout=10000)
    assert page.locator("#releases-translate-all").is_visible()   # 0.9.0 待翻

    # ---- 有预翻译版本: 双向往返, 不得触发机翻 ----
    first = page.locator("#releases-section .rel-item").first
    assert "修复了东西" in first.inner_text()
    assert first.locator(".rel-tr").inner_text().strip() == "原文"
    first.locator(".rel-tr").click()                               # → 原文
    assert "Fixed stuff" in first.inner_text()
    assert first.locator(".rel-tr").inner_text().strip() == "中文译文"
    first.locator(".rel-tr").click()                               # → 切回现成译文(同步)
    assert "修复了东西" in first.inner_text()
    assert first.locator(".rel-tr").inner_text().strip() == "原文"
    assert ms_calls == []                                          # 关键: 全程 0 次机翻

    # ---- 无预翻译版本: 机翻 1 次, 此后往返用缓存 ----
    second = page.locator("#releases-section .rel-item").nth(1)
    assert second.locator(".rel-tr").inner_text().strip() == "翻译"
    second.locator(".rel-tr").click()                              # → 机翻
    second.locator(".rel-tr", has_text="原文").wait_for(timeout=10000)
    assert "机翻结果" in second.inner_text()
    assert len(ms_calls) == 1
    second.locator(".rel-tr").click()                              # → 原文
    assert "Initial release" in second.inner_text()
    assert second.locator(".rel-tr").inner_text().strip() == "中文译文"
    second.locator(".rel-tr").click()                              # → 复用缓存切回
    assert "机翻结果" in second.inner_text()
    assert second.locator(".rel-tr").inner_text().strip() == "原文"
    assert len(ms_calls) == 1                                      # 仍只有首次请求
    assert page.locator("#releases-translate-all").is_hidden()     # 全部已翻 → 按钮隐藏


def test_detail_share_button_feedback(page, site_server):
    """分享按钮: 点击→"已复制链接"反馈→约 2 秒后自动恢复原文案。"""
    page.add_init_script(
        "Object.defineProperty(navigator, 'clipboard', "
        "{value: {writeText: () => Promise.resolve()}, configurable: true});"
        "Object.defineProperty(navigator, 'share', {value: undefined, configurable: true});")
    page.goto(site_server + "/mod/xen.NewHorizons.html")
    page.wait_for_selector("#share-btn")
    label0 = page.locator("#share-btn").inner_text()
    page.click("#share-btn")
    page.wait_for_timeout(400)
    assert "已复制" in page.locator("#share-btn").inner_text()
    page.wait_for_timeout(2300)
    assert page.locator("#share-btn").inner_text() == label0


def test_detail_mermaid_not_loaded_without_diagram(page, site_server):
    """无图表的详情页不得加载 mermaid(~3MB) —— 按需加载器不得误触发(回归: 曾全站静态加载, DCL 4.2s)。"""
    page.goto(site_server + "/mod/Tlya.OnlyTH.html")
    page.wait_for_selector("#detail h1")
    page.wait_for_timeout(2500)          # README 渲染流程完全结束
    assert page.evaluate("typeof window.mermaid") == "undefined"


def test_detail_mermaid_renders_when_needed(page, site_server):
    """更新说明含 ```mermaid 代码块时: 动态拉取并渲染为 SVG(按需路径闭环)。"""
    import json as _json

    fake = ("window.mermaid = { initialize(){}, "
            "render: async () => '<svg class=\"fake-mermaid\"></svg>' };")
    page.route(re.compile(r"cdn\.jsdelivr\.net.*mermaid"), lambda route: route.fulfill(
        status=200, content_type="application/javascript", body=fake))
    rels = {"releases": [{"tag": "1.0.0", "name": "1.0.0", "date": "2026-01-01",
                          "body": "```mermaid\ngraph TD; A-->B;\n```", "bodyZh": ""}]}
    page.route("**/releases/xen.NewHorizons.json*", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=_json.dumps(rels, ensure_ascii=False)))
    page.goto(site_server + "/mod/xen.NewHorizons.html")
    page.wait_for_selector("#detail h1")
    page.locator("#releases-section").scroll_into_view_if_needed()
    page.locator("#releases-section .rel-body").first.wait_for(timeout=10000)
    page.locator("#releases-section svg.fake-mermaid").wait_for(timeout=10000)


def test_home_cta_buttons_no_overlap_and_contained(page, site_server):
    """首页/管理器页 CTA 按钮: 换行时不得互相重叠, 且不得溢出所在区块(防行高塌陷回归)。"""
    for path, sec_id in (("/index.html", "community"), ("/index.html", "contribute"),
                         ("/mod-manager.html", None)):
        page.goto(site_server + path)
        page.wait_for_timeout(600)
        scope = f"#{sec_id} " if sec_id else ""
        rects = page.locator(f"{scope}.cta-row .cta").evaluate_all("""els => els.map(e => {
            const r = e.getBoundingClientRect();
            return [r.x, r.y, r.right, r.bottom];
        })""")
        assert len(rects) >= 2, f"{path}{scope} 按钮数异常"
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                assert not (a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]), \
                    f"{path} 按钮 {i} 与 {j} 重叠: {a} {b}"
        if sec_id:
            contained = page.evaluate(f"""() => {{
                const s = document.getElementById('{sec_id}');
                const sr = s.getBoundingClientRect();
                return [...s.querySelectorAll('.cta')].every(
                    e => e.getBoundingClientRect().bottom <= sr.bottom + 0.5);
            }}""")
            assert contained is True, f"#{sec_id} 按钮溢出区块边界"


def test_turbo_navigates_without_full_reload(page, site_server):
    """Turbo 无刷新导航: 列表↔详情切换不触发整页加载(导航条目始终为 1), 且零 JS 错误。"""
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)[:120]))
    NAV = "performance.getEntriesByType('navigation').length"
    page.goto(site_server + "/mods.html")
    page.wait_for_selector(".mod-card")
    assert page.evaluate(NAV) == 1
    page.locator(".mod-card").first.click()
    page.wait_for_selector("#detail h1")
    page.wait_for_timeout(1800)
    assert page.evaluate(NAV) == 1                     # 关键: 未发生真导航(否则 +1)
    assert page.locator("#detail h1").first.inner_text()
    page.click("nav a[href='mods.html']")
    page.wait_for_selector(".mod-card")
    page.wait_for_timeout(600)
    assert page.evaluate(NAV) == 1
    assert page.locator(".mod-card").count() > 50
    assert errors == []


def test_turbo_back_forward_restores_content(page, site_server):
    """Turbo 后退/前进: 内容正确恢复, 且全程不发生整页加载。"""
    NAV = "performance.getEntriesByType('navigation').length"
    page.goto(site_server + "/mods.html")
    page.wait_for_selector(".mod-card")
    page.locator(".mod-card").first.click()
    page.wait_for_selector("#detail h1")
    page.wait_for_timeout(1500)
    detail_url = page.url
    page.go_back()
    page.wait_for_selector(".mod-card")
    page.wait_for_timeout(800)
    assert "/mods.html" in page.url
    assert page.locator(".mod-card").count() > 50
    page.go_forward()
    page.wait_for_selector("#detail h1")
    page.wait_for_timeout(1500)
    assert page.url == detail_url
    assert page.evaluate(NAV) == 1


def test_to_top_button(page, site_server):
    """滚动超过阈值后[回顶]出现, 点击回到顶部。"""
    page.goto(site_server + "/mod/xen.NewHorizons.html")
    page.wait_for_selector("#detail h1")
    assert page.locator(".to-top.show").count() == 0
    page.locator("#readme-section").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    assert page.locator(".to-top.show").count() == 1
    page.click(".to-top")
    page.wait_for_timeout(900)
    assert page.evaluate("window.scrollY") < 10


def test_detail_trend_chart_with_data_and_labels_inside(page, site_server):
    """趋势图有数据态: 折线渲染, 且所有文本标签几何上不越出画布(防裁剪回归)。"""
    import json as _json
    import time as _time

    now = int(_time.time())
    rows = [{"DownloadCount": 50 * i * i, "UnixTimestamp": now - (60 - i) * 86400}
            for i in range(1, 61)]
    page.route(re.compile(r"outerwildsmods\.com"), lambda route: route.fulfill(
        status=200, content_type="application/json", body=_json.dumps(rows)))
    page.goto(site_server + "/mod/xen.NewHorizons.html")
    page.wait_for_selector("#detail h1")
    page.locator("#trend-section").scroll_into_view_if_needed()
    page.wait_for_timeout(1200)
    assert page.locator("#trend-section svg polyline").count() == 1
    inside = page.evaluate("""() => {
      const svg = document.querySelector('#trend-section svg');
      const vb = svg.viewBox.baseVal;
      return [...svg.querySelectorAll('text')].every(t => {
        const b = t.getBBox();
        return b.x >= 0 && b.y >= 0 && b.x + b.width <= vb.width && b.y + b.height <= vb.height;
      });
    }""")
    assert inside is True
