# <img src="https://img.icons8.com/color/48/xiaohongshu.png" width="28" align="top"> 小红书 MCP Server

> 让 AI 助手无缝对接小红书 —— 搜索笔记、获取详情、查看用户、发布内容，一行命令接入。

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-Protocol-blueviolet)](https://modelcontextprotocol.io)
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
| **当前用户** | 获取已登录账号的信息 | ✅ |

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    使用方式                           │
│                                                     │
│   Claude Code ──stdio──┐                            │
│                        ▼                            │
│   OpenClaw ────SSE────► MCP Server (server.py)      │
│                        │                            │
│   浏览器 ─────HTTP────► Web 面板 (web_panel.py)      │
│                        │                            │
│                        ▼                            │
│              XhsAPI (xhs_client.py)                 │
│              ┌─────────┴──────────┐                 │
│              │  智能延迟  UA 轮换  │                 │
│              └─────────┬──────────┘                 │
│                        ▼                            │
│              签名服务 (sign_server.py)               │
│                        │                            │
│                        ▼                            │
│                   小红书 API                         │
└─────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装

```bash
git clone https://github.com/guoqihan342-svg/xiaohongshu-mcp.git
cd xiaohongshu-mcp
pip install -e .
```

### 2. 启动签名服务

MCP Server 依赖签名服务生成请求头（基于 [xhs](https://github.com/ReaJason/xhs) 库）：

```bash
python sign_server.py
# 默认监听 http://localhost:5555/sign
```

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
```

**OpenClaw（通过 MCPorter）：**

```bash
# 启动 SSE 服务
python server.py --transport sse --port 18060

# 在 OpenClaw 中注册
openclaw mcp add --transport sse xiaohongshu http://127.0.0.1:18060/sse
```

### 4. 一键启动全部服务

```bash
python start.py
```

同时启动签名服务 + Web 管理面板 + MCP HTTP 服务，终端会显示所有服务地址。

## Web 管理面板

启动后访问 `http://127.0.0.1:8080`，提供可视化操作界面：

- **搜索笔记** — 关键词搜索 + 筛选排序 + 笔记详情弹窗
- **用户查询** — 输入用户 ID 查看资料和笔记列表
- **发布笔记** — 图文/视频笔记发布（拖拽上传）
- **设置** — 服务状态监控 + Cookie 管理
- **暗色模式** — 跟随系统或手动切换
- **搜索历史** — 本地记录最近 10 次搜索

## 反爬机制

内置两层防护，降低被风控概率：

**智能延迟系统（HumanBehavior）**
- 基础随机延迟 1~3 秒
- 连续请求时延迟递增（模拟疲劳），每次 +0.3s，上限 +2.5s
- 空闲 60 秒后自动重置（模拟新会话）
- 8% 概率触发 5~12 秒长暂停（模拟"发呆"）

**随机 User-Agent**
- 7 个真实浏览器 UA（Chrome/Edge，Windows/macOS）
- 每次启动随机选取

## Cookie 登录

发布笔记和获取自身信息需要登录态。三种方式获取 Cookie：

```bash
# 方式 1：扫码登录（自动保存到 cookie.txt）
python login.py

# 方式 2：环境变量
export XHS_COOKIE="你的cookie字符串"

# 方式 3：运行时设置（通过 MCP 工具或 Web 面板）
# Cookie 会自动持久化到 cookie.txt，重启不丢失
```

Cookie 需包含 `a1` 和 `web_session` 字段，从浏览器 F12 开发者工具中复制。

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
├── config.py          # 配置管理 + Cookie 持久化
├── utils.py           # 共享验证函数
├── sign_server.py     # Playwright 签名服务
├── web_panel.py       # Flask Web 管理面板
├── login.py           # 浏览器扫码登录
├── start.py           # 一键启动脚本
├── test_all.py        # 测试套件（69 项测试）
├── templates/
│   └── index.html     # 前端页面（暗色模式 + 搜索历史）
├── pyproject.toml     # 项目依赖
└── CLAUDE.md          # AI 助手指引
```

## 测试

```bash
python test_all.py
```

覆盖模块导入、配置解析、参数验证、延迟系统、UA 轮换、API 初始化、Web 路由、MCP 工具注册、文件语法等 69 项检查。

## 致谢

- [xhs](https://github.com/ReaJason/xhs) — 小红书 Python SDK
- [MCP](https://modelcontextprotocol.io) — Model Context Protocol
- [Tailwind CSS](https://tailwindcss.com) — 前端样式框架

## 许可

MIT License
