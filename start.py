"""一键启动 — 签名服务 + Web 管理面板 + MCP HTTP 服务"""

import os
import sys
import signal
import subprocess
import time
import argparse

import httpx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIGN_URL = os.environ.get("XHS_SIGN_URL", "http://localhost:5555/sign")
PYTHON = sys.executable

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


def main():
    global sign_proc, web_proc, mcp_proc

    parser = argparse.ArgumentParser(description="小红书一键启动")
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
    args = parser.parse_args()

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

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
        sign_proc = subprocess.Popen(
            [PYTHON, os.path.join(BASE_DIR, "sign_server.py")],
            cwd=BASE_DIR,
        )
        print("等待签名服务就绪...")
        if wait_for_sign_service():
            print("签名服务已就绪")
        else:
            print("警告：签名服务启动超时，继续启动其他服务")

    # 2. Web 管理面板
    print("正在启动 Web 管理面板...")
    web_proc = subprocess.Popen(
        [PYTHON, os.path.join(BASE_DIR, "web_panel.py")],
        cwd=BASE_DIR,
    )

    # 3. MCP HTTP 服务（用于 OpenClaw 等外部对接）
    if not args.no_mcp:
        print(f"正在启动 MCP 服务（{args.mcp_transport}, 端口 {args.mcp_port}）...")
        mcp_proc = subprocess.Popen(
            [
                PYTHON, os.path.join(BASE_DIR, "server.py"),
                "--transport", args.mcp_transport,
                "--port", str(args.mcp_port),
            ],
            cwd=BASE_DIR,
        )

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
            if web_proc.poll() is not None:
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
