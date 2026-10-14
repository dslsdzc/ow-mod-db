"""端到端测试环境: 构建产物(dist/)起本地服务, 用 Playwright 驱动真实浏览器。"""

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="需要 playwright(本地: pip install playwright && playwright install chromium)")

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST = REPO_ROOT / "dist"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def site_server():
    """dist/ 静态服务(多线程, 避免浏览器并行请求排队超时); 未构建时跳过。"""
    if not (DIST / "index.html").exists():
        pytest.skip("dist/ 不存在,请先运行 python scripts/build.py")
    port = _free_port()
    # 注意: 必须线程化——单线程 http.server 会让浏览器并行资源请求排队, 造成随机超时
    snippet = (
        "import functools, http.server, sys; "
        "h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=sys.argv[2]); "
        "httpd = http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), h); "
        "httpd.serve_forever()")
    proc = subprocess.Popen(
        [sys.executable, "-c", snippet, str(port), str(DIST)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/index.html", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = _launch_chromium(p)
        yield b
        b.close()


def _launch_chromium(p):
    """优先 playwright 自带 Chromium; 缺下载时回退系统浏览器(本地无下载环境)。

    可用 E2E_CHROMIUM_PATH 显式指定浏览器可执行文件。
    """
    import os
    exe = os.environ.get("E2E_CHROMIUM_PATH")
    if exe:
        return p.chromium.launch(executable_path=exe)
    try:
        return p.chromium.launch()
    except Exception:
        for path in ("/usr/bin/chromium", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser"):
            if os.path.exists(path):
                return p.chromium.launch(executable_path=path)
        raise


@pytest.fixture()
def page(browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    yield pg
    ctx.close()
