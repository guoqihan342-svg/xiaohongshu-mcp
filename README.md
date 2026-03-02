# 小红书 MCP Server

> 让 AI 助手无缝对接小红书 —— 搜索笔记、获取详情、查看用户、发布内容，一行命令接入。
> 内置 Scrapling 隐身爬取引擎，API 被封时自动降级为浏览器直接抓取。

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-Protocol-blueviolet)](https://modelcontextprotocol.io)
[![Scrapling](https://img.shields.io/badge/Scrapling-Stealth-purple)](https://github.com/D4Vinci/Scrapling)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 功能一览

| 能力 | 说明 | 需要登录 |
|------|------|:--------:|
| **搜索笔记** | 关键词搜索，支持排序（综合/最热/最新）和类型筛选（全部/图文/视频） | |
| **笔记详情** | 获取完整正文、图片列表、点赞/收藏/评论数据 | |
| **用户信息** | 获取头像、昵称、简介、粉丝数等 | |
| **用户笔记** | 分页获取指定用户的笔记列表 | |
| **发布图文** | 上传图片 + 标题正文，创建图文笔记 | ✅ |
| **发布视频** | 上传视频 + 可选封面，创建视频笔记 | ✅ |
| **Cookie 管理** | 运行时设置 Cookie，自动持久化 | — |
| **扫码登录** | 二维码扫码登录，自动保存 Cookie | — |
| **当前用户** | 获取已登录账号的信息 | ✅ |
| **隐身爬取笔记** | Scrapling 隐身浏览器直接爬取笔记页面（API 备用） | |
| **隐身搜索** | Scrapling 隐身浏览器直接搜索（API 备用） | |
| **通用网页抓取** | TLS 指纹伪装 HTTP 或隐身浏览器抓取任意网页 | |

## 架构概览

```
┌──────────────────────────────────────────────────────────┐
│                      使用方式                              │
│                                                          │
│   Claude Code ──stdio──┐                                 │
│                        ▼                                 │
│   OpenClaw ────SSE────► MCP Server (server.py)           │
│                        │                                 │
│   浏览器 ─────HTTP────► Web 面板 (web_panel.py)           │
│                        │                                 │
│              ┌─────────┴──────────┐                      │
│              ▼                    ▼                       │
│    XhsAPI (xhs_client.py)   Scrapling (scraper.py)       │
│    ┌──────────────────┐     ┌──────────────────────┐     │
│    │ 智能延迟  UA 轮换 │     │ TLS指纹  隐身浏览器  │     │
│    └────────┬─────────┘     │ curl_cffi  Patchright │     │
│             ▼               └──────────────────────┘     │
│    签名服务 (sign_server.py)                              │
│    Patchright 隐身浏览器                                   │
│             ▼                                            │
│        小红书 API                                         │
└──────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装

```bash
git clone https://github.com/guoqihan342-svg/xiaohongshu-mcp.git
cd xiaohongshu-mcp
pip install -e .

# 安装浏览器引擎（签名服务 + 隐身爬取需要）
patchright install chromium
scrapling install
```

### 2. 一键启动全部服务

```bash
python start.py
```

同时启动签名服务 + Web 管理面板 + MCP HTTP 服务，终端会显示所有服务地址。

### 3. 接入 AI 助手

**Claude Code（推荐）：**

```bash
# 注册 MCP 工具
claude mcp add xiaohongshu -- python server.py

# 带 Cookie（可发布笔记）
claude mcp add xiaohongshu -e XHS_COOKIE="你的cookie" -- python server.py
```

注册后直接在 Claude Code 中对话即可使用：

```
> 帮我搜索"旅行攻略"相关的小红书笔记
> 获取这个笔记的详情：6xxxxxxxxxxxxxx
> 查看用户 5xxxxxxxxxxxxxx 的信息
> 用隐身模式搜索"美食推荐"
```

**OpenClaw（通过 MCPorter）：**

```bash
# 启动 SSE 服务
python server.py --transport sse --port 18060

# 在 OpenClaw 中注册
openclaw mcp add --transport sse xiaohongshu http://127.0.0.1:18060/sse
```

## Web 管理面板

启动后访问 `http://127.0.0.1:8080`，提供可视化操作界面：

- **搜索笔记** — 关键词搜索 + 筛选排序 + 笔记详情弹窗 + **隐身搜索**备用
- **用户查询** — 输入用户 ID 查看资料和笔记列表
- **发布笔记** — 图文/视频笔记发布（拖拽上传）
- **设置** — 服务状态监控 + 扫码登录 + Cookie 管理
- **暗色模式** — 跟随系统或手动切换
- **搜索历史** — 本地记录最近 10 次搜索

## 反爬机制

内置多层防护，降低被风控概率：

**签名服务（Patchright 隐身浏览器）**
- 使用 [Patchright](https://github.com/AresS31/patchright)（Playwright 隐身分支），内置反检测
- 无需手动注入 stealth.js，比 playwright-stealth 更全面
- 自动处理 canvas 指纹、WebRTC 泄露、navigator.webdriver 等检测点

**Scrapling 增强爬取**
- [Scrapling](https://github.com/D4Vinci/Scrapling) 提供 TLS 指纹伪装（curl_cffi）和隐身浏览器
- HTTP 请求级别：模拟真实浏览器 TLS 握手（JA3 指纹），WAF 无法区分
- 浏览器级别：Patchright + browserforge + canvas noise + WebRTC 拦截
- 当 API 被封（300011/300015 错误）时，自动降级为浏览器直接爬取

**智能延迟系统（HumanBehavior）**
- 基础随机延迟 1~3 秒
- 连续请求时延迟递增（模拟疲劳），每次 +0.3s，上限 +2.5s
- 空闲 60 秒后自动重置（模拟新会话）
- 8% 概率触发 5~12 秒长暂停（模拟"发呆"）

**随机 User-Agent**
- 7 个真实浏览器 UA（Chrome/Edge，Windows/macOS）
- 每次启动随机选取

## Cookie 登录

发布笔记和获取自身信息需要登录态。三种方式：

```bash
# 方式 1：Web 面板扫码登录（推荐）
python start.py
# 打开 http://127.0.0.1:8080 → 设置 → 生成二维码 → 手机扫码

# 方式 2：命令行扫码登录
python login.py

# 方式 3：环境变量
export XHS_COOKIE="你的cookie字符串"
```

Cookie 需包含 `a1` 和 `web_session` 字段。登录成功后 Cookie 自动持久化到 `cookie.txt`，重启不丢失。

## MCP 工具列表

| 工具 | 说明 | 引擎 |
|------|------|------|
| `search_notes` | 搜索笔记 | xhs API |
| `get_note_detail` | 笔记详情 | xhs API |
| `get_user_info` | 用户信息 | xhs API |
| `get_user_notes` | 用户笔记列表 | xhs API |
| `create_note` | 发布图文笔记 | xhs API |
| `create_video_note` | 发布视频笔记 | xhs API |
| `set_cookie` | 设置 Cookie | — |
| `get_self_info` | 当前用户信息 | xhs API |
| `qrcode_login` | 生成登录二维码 | xhs API |
| `check_qrcode` | 检查扫码状态 | xhs API |
| `scrape_note` | 隐身爬取笔记页面 | Scrapling |
| `scrape_search_notes` | 隐身搜索笔记 | Scrapling |
| `scrape_webpage` | 通用网页抓取 | Scrapling |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `XHS_COOKIE` | 小红书 Cookie | 空（无登录模式） |
| `XHS_SIGN_URL` | 签名服务地址 | `http://localhost:5555/sign` |
| `XHS_TIMEOUT` | 请求超时（秒） | `10` |
| `MCP_PORT` | MCP HTTP 端口 | `18060` |

## 项目结构

```
xiaohongshu-mcp/
├── server.py          # MCP Server 入口（stdio / SSE / streamable-http）
├── xhs_client.py      # 小红书 API 客户端（智能延迟 + UA 轮换）
├── scraper.py         # Scrapling 增强爬取模块（TLS 伪装 + 隐身浏览器）
├── config.py          # 配置管理 + Cookie 持久化
├── utils.py           # 共享验证函数
├── sign_server.py     # Patchright 隐身签名服务
├── web_panel.py       # Flask Web 管理面板
├── login.py           # 浏览器扫码登录
├── start.py           # 一键启动脚本
├── test_all.py        # 测试套件（93 项测试）
├── templates/
│   └── index.html     # 前端页面（暗色模式 + 搜索历史 + 隐身搜索）
├── pyproject.toml     # 项目依赖
└── CLAUDE.md          # AI 助手指引
```

## 测试

```bash
python test_all.py
```

覆盖模块导入、配置解析、参数验证、延迟系统、UA 轮换、API 初始化、Scrapling 模块、Web 路由、MCP 工具注册、文件语法、依赖完整性等 93 项检查。

## 致谢

- [xhs](https://github.com/ReaJason/xhs) — 小红书 Python SDK
- [Scrapling](https://github.com/D4Vinci/Scrapling) — 隐身爬取框架（curl_cffi + Patchright）
- [MCP](https://modelcontextprotocol.io) — Model Context Protocol
- [Tailwind CSS](https://tailwindcss.com) — 前端样式框架

## 许可

MIT License
