"""小红书 MCP Server 配置模块"""

import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cookie 持久化文件
COOKIE_FILE = os.path.join(BASE_DIR, "cookie.txt")

# 签名服务地址
XHS_SIGN_URL = os.environ.get("XHS_SIGN_URL", "http://localhost:5555/sign")

# 请求超时时间（秒）
_DEFAULT_TIMEOUT = 10
try:
    REQUEST_TIMEOUT = int(os.environ.get("XHS_TIMEOUT", str(_DEFAULT_TIMEOUT)))
    if REQUEST_TIMEOUT <= 0:
        REQUEST_TIMEOUT = _DEFAULT_TIMEOUT
except ValueError:
    REQUEST_TIMEOUT = _DEFAULT_TIMEOUT


def load_cookie() -> str:
    """加载 Cookie：优先环境变量，其次 cookie.txt"""
    cookie = os.environ.get("XHS_COOKIE", "")
    if cookie:
        return cookie
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def save_cookie(cookie: str):
    """保存 Cookie 到 cookie.txt"""
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        f.write(cookie)


# MCP HTTP 服务端口（用于 SSE / streamable-http 传输）
_DEFAULT_MCP_PORT = 18060
try:
    MCP_PORT = int(os.environ.get("MCP_PORT", str(_DEFAULT_MCP_PORT)))
    if MCP_PORT <= 0 or MCP_PORT > 65535:
        MCP_PORT = _DEFAULT_MCP_PORT
except ValueError:
    MCP_PORT = _DEFAULT_MCP_PORT

XHS_COOKIE = load_cookie()
