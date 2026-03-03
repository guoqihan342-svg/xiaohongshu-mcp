"""一键启动 — 签名服务 + Web 管理面板 + MCP HTTP 服务

支持两种运行模式：
- 编排模式（默认）：启动所有服务的子进程
- 服务模式（--service）：直接运行指定服务（供 EXE 内部调度使用）
"""

import os
import sys
import signal
import subprocess
import time
import argparse

import httpx

# frozen exe 时取 exe 所在目录
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SIGN_URL = os.environ.get("XHS_SIGN_URL", "http://localhost:5555/sign")


def _ensure_browsers():
    """确保 Playwright Chromium 已安装（首次运行时自动下载）"""
    import glob

    if getattr(sys, "frozen", False):
        # ── frozen EXE 模式 ──────────────────────────────────────────
        # 1. 先设置浏览器目录（必须在任何 playwright 调用之前）
        browsers_dir = os.path.join(BASE_DIR, "browsers")
        os.makedirs(browsers_dir, exist_ok=True)
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_dir

        # 2. 已有 chromium 则跳过
        if glob.glob(os.path.join(browsers_dir, "chromium*")):
            return

        # 3. 用打包进来的 node.exe + package/cli.js 安装
        meipass = getattr(sys, "_MEIPASS", "")
        node = os.path.join(meipass, "playwright", "driver", "node.exe")
        cli  = os.path.join(meipass, "playwright", "driver", "package", "cli.js")

        if not os.path.exists(node) or not os.path.exists(cli):
            print("警告：找不到 Playwright 驱动，签名服务可能无法启动")
            return

        print("首次运行，正在下载 Chromium 浏览器（约 150MB）...")
        try:
            subprocess.run(
                [node, cli, "install", "chromium"],
                env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": browsers_dir},
                timeout=300, check=True,
            )
            print("Chromium 下载完成")
        except Exception as e:
            print(f"警告：Chromium 下载失败（{e}），请手动运行：playwright install chromium")

    else:
        # ── 开发模式 ─────────────────────────────────────────────────
        try:
            from playwright._impl._driver import compute_driver_executable
            driver = str(compute_driver_executable())
            result = subprocess.run(
                [driver, "install", "--dry-run", "chromium"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 or "chromium" not in result.stdout.lower():
                print("正在下载 Chromium 浏览器（约 150MB）...")
                subprocess.run([driver, "install", "chromium"], timeout=300, check=True)
                print("Chromium 下载完成")
        except Exception as e:
            print(f"警告：浏览器检查失败（{e}），签名服务可能无法启动")


sign_proc = None
web_proc = None
mcp_proc = None


def cleanup(*_):
    """优雅退出，关闭所有子进程"""
    for name, proc in [
        ("MCP 服务", mcp_proc),
        ("Web 面板", web_proc),
        ("签名服务", sign_proc),
    ]:
        if proc and proc.poll() is None:
            print(f"正在关闭 {name}...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("已退出")
    sys.exit(0)


def wait_for_sign_service(timeout=60):
    """等待签名服务就绪"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.post(SIGN_URL,
                              json={"uri": "/test", "data": "", "a1": "", "web_session": ""},
                              timeout=3)
            if resp.status_code in (200, 400):
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def wait_for_http(url, timeout=30):
    """等待 HTTP 服务就绪"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(url, timeout=3)
            if resp.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _spawn(service_args: list[str]) -> subprocess.Popen:
    """启动子进程：frozen 模式用 exe --service，否则用 python 脚本"""
    exe = sys.executable
    if getattr(sys, "frozen", False):
        cmd = [exe] + service_args
    else:
        cmd = [exe] + service_args
    return subprocess.Popen(cmd, cwd=BASE_DIR)


def run_service(service_name: str, extra_args: list[str]):
    """直接运行指定服务（--service 模式，每个服务在独立进程中）"""
    # 确保模块搜索路径包含项目目录
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)

    if service_name == "sign":
        import sign_server
        sign_server.app.run(host="127.0.0.1", port=5555)

    elif service_name == "web":
        import web_panel
        web_panel.app.run(host="127.0.0.1", port=8080, debug=False)

    elif service_name == "mcp":
        p = argparse.ArgumentParser()
        p.add_argument("--transport", default="sse")
        p.add_argument("--port", type=int, default=18060)
        p.add_argument("--host", default="127.0.0.1")
        mcp_args = p.parse_args(extra_args)

        import server as mcp_server
        if mcp_args.transport in ("sse", "streamable-http"):
            mcp_server.mcp.settings.host = mcp_args.host
            mcp_server.mcp.settings.port = mcp_args.port
        mcp_server.mcp.run(transport=mcp_args.transport)

    else:
        print(f"未知服务: {service_name}")
        sys.exit(1)


def main():
    global sign_proc, web_proc, mcp_proc

    parser = argparse.ArgumentParser(description="小红书一键启动")
    parser.add_argument(
        "--service", choices=["sign", "web", "mcp"],
        help="直接运行指定服务（内部调度用）",
    )
    parser.add_argument(
        "--no-mcp", action="store_true",
        help="不启动 MCP HTTP 服务",
    )
    parser.add_argument(
        "--mcp-transport", choices=["sse", "streamable-http"],
        default="sse", help="MCP 传输方式（默认 sse）",
    )
    parser.add_argument(
        "--mcp-port", type=int, default=18060,
        help="MCP HTTP 服务端口（默认 18060）",
    )
    args, remaining = parser.parse_known_args()

    # --service 模式：直接运行指定服务
    if args.service:
        run_service(args.service, remaining)
        return

    # ===== 编排模式：启动所有子进程 =====
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # 0. 确保 Playwright Chromium 已安装（首次运行自动下载）
    _ensure_browsers()

    # 1. 签名服务
    sign_already_running = False
    try:
        resp = httpx.post(SIGN_URL,
                          json={"uri": "/test", "data": "", "a1": "", "web_session": ""},
                          timeout=2)
        if resp.status_code in (200, 400):
            sign_already_running = True
            print("签名服务已在运行，跳过启动")
    except Exception:
        pass

    if not sign_already_running:
        print("正在启动签名服务...")
        if getattr(sys, "frozen", False):
            sign_proc = _spawn(["--service", "sign"])
        else:
            sign_proc = _spawn([os.path.join(BASE_DIR, "sign_server.py")])
        print("等待签名服务就绪...")
        if wait_for_sign_service():
            print("签名服务已就绪")
        else:
            print("警告：签名服务启动超时，继续启动其他服务")

    # 2. Web 管理面板
    print("正在启动 Web 管理面板...")
    if getattr(sys, "frozen", False):
        web_proc = _spawn(["--service", "web"])
    else:
        web_proc = _spawn([os.path.join(BASE_DIR, "web_panel.py")])

    # 3. MCP HTTP 服务（用于 OpenClaw 等外部对接）
    if not args.no_mcp:
        print(f"正在启动 MCP 服务（{args.mcp_transport}, 端口 {args.mcp_port}）...")
        if getattr(sys, "frozen", False):
            mcp_proc = _spawn([
                "--service", "mcp",
                "--transport", args.mcp_transport,
                "--port", str(args.mcp_port),
            ])
        else:
            mcp_proc = _spawn([
                os.path.join(BASE_DIR, "server.py"),
                "--transport", args.mcp_transport,
                "--port", str(args.mcp_port),
            ])

    mcp_url = f"http://127.0.0.1:{args.mcp_port}"

    print("\n" + "=" * 48)
    print("  小红书服务已启动")
    print(f"  Web 面板:    http://127.0.0.1:8080")
    if not args.no_mcp:
        if args.mcp_transport == "sse":
            print(f"  MCP (SSE):   {mcp_url}/sse")
        else:
            print(f"  MCP (HTTP):  {mcp_url}/mcp")
    print(f"  签名服务:    {SIGN_URL}")
    print("  按 Ctrl+C 退出")
    print("=" * 48)

    if not args.no_mcp:
        print("\n  OpenClaw 对接命令:")
        if args.mcp_transport == "sse":
            print(f"  openclaw mcp add --transport sse xiaohongshu {mcp_url}/sse")
        else:
            print(f"  openclaw mcp add --transport http xiaohongshu {mcp_url}/mcp")

    print()

    # 等待子进程
    try:
        while True:
            if web_proc and web_proc.poll() is not None:
                print("Web 面板已退出")
                break
            if sign_proc and sign_proc.poll() is not None:
                print("签名服务已退出")
                break
            if mcp_proc and mcp_proc.poll() is not None:
                print("MCP 服务已退出")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
