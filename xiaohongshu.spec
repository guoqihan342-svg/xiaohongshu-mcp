# -*- mode: python ; coding: utf-8 -*-
"""小红书 MCP Server — PyInstaller 打包配置

使用方式:
    pip install pyinstaller
    pyinstaller xiaohongshu.spec

或:
    python build.py
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
PROJECT_DIR = os.path.dirname(os.path.abspath(SPEC))

# ===== 收集复杂包的所有子模块和数据 =====

gevent_datas, gevent_binaries, gevent_hiddenimports = collect_all("gevent")
mcp_datas, mcp_binaries, mcp_hiddenimports = collect_all("mcp")

# Playwright / Patchright 驱动文件
pw_datas = []
try:
    import playwright
    pw_path = os.path.dirname(playwright.__file__)
    driver_dir = os.path.join(pw_path, "driver")
    if os.path.isdir(driver_dir):
        pw_datas.append((driver_dir, os.path.join("playwright", "driver")))
except ImportError:
    pass

pr_datas = []
try:
    import patchright
    pr_path = os.path.dirname(patchright.__file__)
    driver_dir = os.path.join(pr_path, "driver")
    if os.path.isdir(driver_dir):
        pr_datas.append((driver_dir, os.path.join("patchright", "driver")))
except ImportError:
    pass

# ===== Hidden imports =====

hiddenimports = [
    # gevent
    *gevent_hiddenimports,
    "greenlet",
    # MCP
    *mcp_hiddenimports,
    # Flask / Jinja2
    "flask", "jinja2", "werkzeug", "markupsafe",
    # XHS SDK
    "xhs", "xhs.exception",
    # HTTP
    "httpx", "httpcore", "anyio", "sniffio",
    # Playwright
    "playwright", "playwright.sync_api", "playwright._impl",
    "playwright_stealth",
    # Scrapling / Patchright
    "scrapling", "patchright", "patchright.sync_api", "curl_cffi",
    # QR code
    "qrcode", "qrcode.image", "qrcode.image.pil",
    # 项目模块
    "config", "utils", "xhs_client", "scraper",
    "server", "sign_server", "web_panel", "login",
]

# ===== 数据文件 =====

datas = [
    (os.path.join(PROJECT_DIR, "templates"), "templates"),
    *gevent_datas,
    *mcp_datas,
    *pw_datas,
    *pr_datas,
]

# ===== Analysis =====

a = Analysis(
    [os.path.join(PROJECT_DIR, "start.py")],
    pathex=[PROJECT_DIR],
    binaries=[*gevent_binaries, *mcp_binaries],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "unittest", "email", "xml", "pydoc",
        "test", "tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="start",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="xiaohongshu-mcp",
)
