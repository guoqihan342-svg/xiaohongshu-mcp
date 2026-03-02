"""小红书签名服务 - 基于 Playwright 生成 x-s/x-t 请求头"""

import logging
import time

from flask import Flask, request, jsonify
from gevent import monkey
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

monkey.patch_all()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

stealth = Stealth()


def get_context_page(instance):
    chromium = instance.chromium
    browser = chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    stealth.apply_stealth_sync(page)
    return context, page


logger.info("正在启动 Playwright...")
playwright = sync_playwright().start()
browser_context, context_page = get_context_page(playwright)

logger.info("正在跳转至小红书首页...")
context_page.goto("https://www.xiaohongshu.com")
time.sleep(3)

context_page.wait_for_load_state("networkidle")
time.sleep(2)

for i in range(10):
    has_sign_fn = context_page.evaluate("() => typeof window._webmsxyw === 'function'")
    if has_sign_fn:
        logger.info("签名函数 _webmsxyw 已就绪")
        break
    logger.info("等待签名函数加载... (%d/10)", i + 1)
    time.sleep(2)
else:
    logger.warning("签名函数未检测到，签名可能失败")

cookies = browser_context.cookies()
for cookie in cookies:
    if cookie["name"] == "a1":
        logger.info("当前浏览器 a1 值: %s", cookie["value"])
        logger.info("请将需要使用的 a1 设置成一样方可签名成功")

logger.info("签名服务就绪，监听 127.0.0.1:5555...")


def sign(uri, data, a1, web_session):
    """调用浏览器签名函数，失败时自动重新加载页面重试"""
    global context_page, browser_context
    try:
        encrypt_params = context_page.evaluate(
            "([url, data]) => window._webmsxyw(url, data)", [uri, data]
        )
    except Exception:
        logger.warning("签名函数调用失败，尝试重新加载页面...")
        try:
            context_page.goto("https://www.xiaohongshu.com/explore",
                              wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)
        except Exception:
            context_page.reload(wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)
        encrypt_params = context_page.evaluate(
            "([url, data]) => window._webmsxyw(url, data)", [uri, data]
        )
    return {
        "x-s": encrypt_params["X-s"],
        "x-t": str(encrypt_params["X-t"]),
    }


@app.route("/sign", methods=["POST"])
def sign_handler():
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": "请求体必须为 JSON 格式"}), 400

    uri = json_data.get("uri")
    if not uri or not isinstance(uri, str):
        return jsonify({"error": "缺少有效的 uri 参数"}), 400

    data = json_data.get("data")
    a1 = json_data.get("a1", "")
    web_session = json_data.get("web_session", "")

    try:
        result = sign(uri, data, a1, web_session)
        return jsonify(result)
    except Exception:
        logger.exception("签名失败")
        return jsonify({"error": "签名执行失败，请检查签名服务状态"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5555)
