# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言要求

- 整个项目使用中文，包括代码注释、文档、提交信息和与用户的交流均使用中文。

## 项目概述

小红书 MCP Server —— 让 Claude Code / OpenClaw 等 AI 助手能够搜索笔记、获取详情、获取用户信息以及发布笔记。

## 项目结构

- `server.py` — MCP Server 入口（支持 stdio / SSE / streamable-http 三种传输）
- `xhs_client.py` — 小红书 API 客户端封装（基于 xhs 库，含智能延迟和 UA 轮换）
- `config.py` — 配置管理（Cookie 持久化、签名服务地址等）
- `utils.py` — 共享验证函数
- `sign_server.py` — Playwright 签名服务
- `web_panel.py` — Flask Web 管理面板
- `login.py` — 浏览器扫码登录
- `start.py` — 一键启动（签名服务 + Web 面板 + MCP HTTP 服务）
- `templates/index.html` — 前端页面（暗色模式 + 搜索历史）

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `XHS_COOKIE` | 小红书 Cookie（登录模式） | 空（无登录模式） |
| `XHS_SIGN_URL` | 签名服务地址 | `http://localhost:5555/sign` |
| `XHS_TIMEOUT` | 请求超时时间（秒） | `10` |
| `MCP_PORT` | MCP HTTP 服务端口 | `18060` |

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
