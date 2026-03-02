"""小红书扫码登录 - 通过 Playwright 浏览器获取 Cookie"""

import os
import time
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

stealth = Stealth()


def main():
    print("正在启动浏览器...")
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=False)  # 有头模式，方便扫码
    try:
        context = browser.new_context()
        page = context.new_page()
        stealth.apply_stealth_sync(page)

        print("正在打开小红书登录页...")
        page.goto("https://www.xiaohongshu.com")
        time.sleep(3)

        print("\n" + "=" * 50)
        print("请在弹出的浏览器窗口中：")
        print("1. 点击「登录」按钮")
        print("2. 用小红书 APP 扫描二维码")
        print("3. 在手机上确认登录")
        print("4. 等待页面跳转完成")
        print("=" * 50)
        print("\n登录成功后会自动检测，请耐心等待...\n")

        # 等待登录成功（检测 web_session cookie）
        for i in range(120):  # 最多等 4 分钟
            cookies = context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies}

            if "web_session" in cookie_dict:
                # 拼接 cookie 字符串
                cookie_str = "; ".join(
                    f"{c['name']}={c['value']}" for c in cookies
                    if c["domain"].endswith("xiaohongshu.com")
                )
                print("\n登录成功！")

                # 保存到文件
                cookie_file = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "cookie.txt"
                )
                try:
                    with open(cookie_file, "w", encoding="utf-8") as f:
                        f.write(cookie_str)
                    print(f"Cookie 已保存到 {cookie_file}")
                except OSError as e:
                    print(f"Cookie 保存失败: {e}")
                    print(f"Cookie 内容: {cookie_str}")
                    break

                # 仅打印预览，不完整暴露
                print(f"Cookie 预览: {cookie_str[:50]}...")
                print("\n使用方式：")
                print('claude mcp add xiaohongshu -e XHS_COOKIE="<见 cookie.txt>"'
                      ' -- python E:/MCP/xiaohongshu/server.py')
                break

            time.sleep(2)
        else:
            print("超时未检测到登录，请重试。")
    finally:
        browser.close()
        pw.stop()


if __name__ == "__main__":
    main()
