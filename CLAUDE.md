# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言要求

整个项目使用中文，包括代码注释、文档、提交信息和与用户的交流均使用中文。

## 项目概述

小红书 MCP Server —— 让 Claude Code / OpenClaw 等 AI 助手能够搜索笔记、获取详情、获取用户信息以及发布笔记。

## 项目结构

- `server.py` — MCP Server 入口（支持 stdio / SSE / streamable-http 三种传输，定义 13 个工具）
- `xhs_client.py` — 小红书 API 客户端（xhs 库封装、HumanBehavior 延迟、UA 轮换、线程安全、签名重试）
- `scraper.py` — Scrapling 增强爬取模块（TLS 指纹伪装 HTTP + Patchright 隐身浏览器，含超时保护）
- `config.py` — 配置管理（Cookie 线程安全持久化、frozen exe 路径支持）
- `utils.py` — 共享验证函数（validate_cookie 要求同时含 a1 和 web_session）
- `sign_server.py` — Playwright + Stealth 签名服务（Flask，端口 5555，含并发锁和重试机制）
- `web_panel.py` — Flask Web 管理面板（端口 8080）
- `login.py` — 浏览器扫码登录脚本（有头模式，等待 web_session，最多 4 分钟）
- `start.py` — 一键启动 + EXE 服务调度（编排 sign/web/mcp 三个子进程，支持 --service 模式）
- `templates/index.html` — 前端页面（暗色模式 + 搜索历史 + 隐身搜索）
- `xiaohongshu.spec` — PyInstaller 打包配置
- `build.py` — EXE 构建脚本

## MCP 工具列表（13 个）

| 工具 | 说明 | 是否需要 Cookie |
|------|------|--------------|
| `search_notes` | 搜索笔记（sort: general/popular/latest，note_type: all/video/image） | 否 |
| `get_note_detail` | 获取笔记详情 | 否 |
| `get_user_info` | 获取用户信息 | 否 |
| `get_user_notes` | 获取用户笔记列表（cursor 分页） | 否 |
| `set_cookie` | 设置 Cookie 并持久化到 cookie.txt | 否 |
| `get_self_info` | 获取当前登录用户信息 | 是 |
| `qrcode_login` | 生成扫码登录二维码，返回 qr_id/code/url | 否 |
| `check_qrcode` | 轮询扫码状态（code_status: 0=未扫 1=待确认 2=已登录） | 否 |
| `create_note` | 发布图文笔记（image_paths[] 为本地路径） | 是 |
| `create_video_note` | 发布视频笔记（cover_path 空则用首帧） | 是 |
| `scrape_note` | Patchright 隐身浏览器爬取笔记（API 被封备用） | 否 |
| `scrape_search_notes` | Patchright 隐身浏览器搜索笔记（API 被封备用） | 否 |
| `scrape_webpage` | 通用爬取（use_browser=False: HTTP TLS 伪装，True: 隐身浏览器） | 否 |

## 两种运行模式

**无 Cookie（只读模式）**：可用搜索、获取详情/用户信息；依赖签名服务生成 x-s/x-t 请求头。

**有 Cookie（登录模式）**：额外支持发布笔记、获取自身信息；启动时自动从签名服务 `/a1` 接口同步浏览器 a1 值——若 a1 不匹配则更新 Cookie 中的 a1 并清除 web_session，提示重新扫码。

Cookie 验证要求：必须同时包含 `a1` 和 `web_session` 字段。

## 降级策略

xhs API 调用失败时，用户可手动调用 `scrape_note` / `scrape_search_notes` 工具，通过 Scrapling 隐身浏览器直接爬取：
1. 优先从 SSR 数据 `window.__INITIAL_STATE__` 提取
2. 降级到 CSS 选择器 DOM 提取

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `XHS_COOKIE` | 小红书 Cookie（优先级高于 cookie.txt） | 空（无登录模式） |
| `XHS_SIGN_URL` | 签名服务地址 | `http://localhost:5555/sign` |
| `XHS_TIMEOUT` | 请求超时时间（秒） | `10` |
| `MCP_PORT` | MCP HTTP 服务端口 | `18060` |

内部固定端口：签名服务 `5555`，Web 面板 `8080`。

## 构建和运行

```bash
# 安装依赖
pip install -e .

# 一键启动（签名服务 + Web 面板 + MCP SSE 服务）
python start.py

# 仅启动 MCP Server（stdio 模式，用于 Claude Code）
python server.py

# MCP Server SSE 模式（用于 OpenClaw 对接）
python server.py --transport sse --port 18060

# 构建 EXE（输出到 dist/xiaohongshu-mcp/start.exe）
pip install pyinstaller
python build.py
```


## 注册到 Claude Code

```bash
claude mcp add xiaohongshu -- python E:/MCP/xiaohongshu/server.py
```

带 Cookie 启动：

```bash
claude mcp add xiaohongshu -e XHS_COOKIE="你的cookie" -- python E:/MCP/xiaohongshu/server.py
```

## 对接 OpenClaw

```bash
# 1. 先启动服务（包含 MCP SSE）
python start.py

# 2. 在 OpenClaw 中注册（通过 MCPorter）
openclaw mcp add --transport sse xiaohongshu http://127.0.0.1:18060/sse
```

## 签名服务

xhs 库需要签名服务来生成请求头。参考 https://github.com/ReaJason/xhs 部署签名服务后，通过 `XHS_SIGN_URL` 环境变量配置地址。

## 稳定性机制

- **线程安全**：HumanBehavior 延迟、签名服务浏览器操作、Cookie 持久化均有 `threading.Lock` 保护
- **签名重试**：HTTP 客户端 3 次重试 + 指数退避（1s/2s/4s）；签名函数 3 次重试 + 页面重载
- **超时保护**：浏览器爬取 30 秒超时、HTTP 爬取 15 秒超时（ThreadPoolExecutor 包装）
- **日志隔离**：MCP stdio 模式仅输出 WARNING 级日志，避免干扰协议
- **HumanBehavior**：基础延迟 1-3s，每次请求额外 +0.3s（上限 2.5s），8% 概率随机发呆 5-12s，60s 无操作重置
