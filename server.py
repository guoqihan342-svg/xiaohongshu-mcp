"""小红书 MCP Server - 让 Claude Code 能够搜索和管理小红书笔记"""

import json
import logging
import sys
import functools
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP, Context
from xhs.exception import DataFetchError, IPBlockError, SignError, NeedVerifyError

import config
from xhs_client import XhsAPI
from scraper import scrape_note_by_url, scrape_search, fetch_url
from utils import (clamp, validate_enum, validate_keyword,
                   validate_id, validate_cookie, validate_file_path)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def _tool_error_handler(func):
    """MCP 工具统一异常处理装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            return _err("参数错误", str(e))
        except IPBlockError:
            return _err("IP 被限流", "请求过于频繁，请稍后再试")
        except SignError as e:
            return _err("签名失败", str(e) or "请检查签名服务是否正常运行")
        except NeedVerifyError:
            return _err("需要验证码", "触发了人机验证，请稍后再试或更换 Cookie")
        except DataFetchError as e:
            return _err("数据获取失败", str(e))
        except RuntimeError as e:
            return _err("操作失败", str(e))
        except Exception as e:
            logger.exception("工具调用异常")
            return _err("未知错误", f"{type(e).__name__}: {e}")
    return wrapper


def _err(error, message):
    return json.dumps({"error": error, "message": message}, ensure_ascii=False)


def _ok(data):
    return json.dumps(data, ensure_ascii=False, indent=2)


# ===== 生命周期 =====

@dataclass
class AppContext:
    xhs: XhsAPI


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    logger.info("小红书 MCP Server 启动中...")
    xhs = XhsAPI()
    logger.info("已初始化（Cookie 模式: %s）", xhs.has_cookie)
    try:
        yield AppContext(xhs=xhs)
    finally:
        logger.info("小红书 MCP Server 已关闭")


mcp = FastMCP("xiaohongshu", lifespan=app_lifespan)


def _xhs(ctx: Context) -> XhsAPI:
    return ctx.request_context.lifespan_context.xhs


# ===== 工具 =====

@mcp.tool()
@_tool_error_handler
def search_notes(keyword: str, page: int = 1, page_size: int = 20,
                 sort: str = "general", note_type: str = "all",
                 ctx: Context = None) -> str:
    """搜索小红书笔记。

    Args:
        keyword: 搜索关键词
        page: 页码,默认 1
        page_size: 每页数量,默认 20
        sort: 排序方式 - general(综合), popular(最热), latest(最新)
        note_type: 笔记类型 - all(全部), video(视频), image(图文)
    """
    return _ok(_xhs(ctx).search_notes(
        keyword=validate_keyword(keyword),
        page=clamp(page, 1, 100, 1),
        page_size=clamp(page_size, 1, 50, 20),
        sort=validate_enum(sort, {"general", "popular", "latest"}, "general"),
        note_type=validate_enum(note_type, {"all", "video", "image"}, "all"),
    ))


@mcp.tool()
@_tool_error_handler
def get_note_detail(note_id: str, ctx: Context = None) -> str:
    """获取小红书笔记详情。

    Args:
        note_id: 笔记 ID
    """
    return _ok(_xhs(ctx).get_note_detail(
        note_id=validate_id(note_id, "笔记 ID")))


@mcp.tool()
@_tool_error_handler
def get_user_info(user_id: str, ctx: Context = None) -> str:
    """获取小红书用户信息。

    Args:
        user_id: 用户 ID
    """
    return _ok(_xhs(ctx).get_user_info(user_id=validate_id(user_id, "用户 ID")))


@mcp.tool()
@_tool_error_handler
def get_user_notes(user_id: str, cursor: str = "",
                   ctx: Context = None) -> str:
    """获取小红书用户的笔记列表。

    Args:
        user_id: 用户 ID
        cursor: 分页游标,首次为空,后续使用返回值中的 cursor
    """
    return _ok(_xhs(ctx).get_user_notes(
        user_id=validate_id(user_id, "用户 ID"), cursor=cursor))


@mcp.tool()
@_tool_error_handler
def create_note(title: str, desc: str, image_paths: list[str],
                is_private: bool = False, ctx: Context = None) -> str:
    """发布小红书图文笔记（需要 Cookie 登录）。

    Args:
        title: 笔记标题
        desc: 笔记正文内容
        image_paths: 图片文件的本地路径列表
        is_private: 是否仅自己可见,默认 False
    """
    if not title.strip():
        raise ValueError("笔记标题不能为空")
    if not image_paths:
        raise ValueError("至少需要一张图片")
    for p in image_paths:
        validate_file_path(p, "图片文件")
    return _ok(_xhs(ctx).create_image_note(
        title=title, desc=desc, image_paths=image_paths, is_private=is_private))


@mcp.tool()
@_tool_error_handler
def create_video_note(title: str, desc: str, video_path: str,
                      cover_path: str = "", is_private: bool = False,
                      ctx: Context = None) -> str:
    """发布小红书视频笔记（需要 Cookie 登录）。

    Args:
        title: 笔记标题
        desc: 笔记正文内容
        video_path: 视频文件的本地路径
        cover_path: 封面图路径,为空则自动提取视频首帧
        is_private: 是否仅自己可见,默认 False
    """
    if not title.strip():
        raise ValueError("笔记标题不能为空")
    validate_file_path(video_path, "视频文件")
    if cover_path:
        validate_file_path(cover_path, "封面图文件")
    return _ok(_xhs(ctx).create_video_note(
        title=title, desc=desc, video_path=video_path,
        cover_path=cover_path or None, is_private=is_private))


@mcp.tool()
@_tool_error_handler
def set_cookie(cookie: str, ctx: Context = None) -> str:
    """设置小红书 Cookie,启用登录模式。从浏览器开发者工具中复制 Cookie 字符串。

    Args:
        cookie: 小红书网站的 Cookie 字符串（需包含 a1 和 web_session）
    """
    _xhs(ctx).set_cookie(validate_cookie(cookie))
    return "Cookie 设置成功，已切换到登录模式"


@mcp.tool()
@_tool_error_handler
def get_self_info(ctx: Context = None) -> str:
    """获取当前登录用户的信息（需要 Cookie 登录）。"""
    return _ok(_xhs(ctx).get_self_info())


@mcp.tool()
@_tool_error_handler
def qrcode_login(ctx: Context = None) -> str:
    """生成小红书扫码登录二维码。返回 qr_id 和 code 用于后续检查扫码状态。
    用户需用小红书 APP 扫描返回的链接对应的二维码,然后调用 check_qrcode 检查登录状态。

    Returns:
        包含 qr_id、code 和 url 的 JSON
    """
    result = _xhs(ctx).create_qrcode()
    url = result.get("url", "")
    if not url:
        return _err("二维码生成失败", "未获取到二维码链接")
    return _ok(result)


@mcp.tool()
@_tool_error_handler
def check_qrcode(qr_id: str, code: str, ctx: Context = None) -> str:
    """检查扫码登录状态。配合 qrcode_login 使用,轮询直到登录成功。

    Args:
        qr_id: qrcode_login 返回的二维码 ID
        code: qrcode_login 返回的验证码
    """
    xhs = _xhs(ctx)
    # xhs_client.check_qrcode 会自动激活会话并保存 Cookie
    result = xhs.check_qrcode(qr_id=qr_id, code=code)
    code_status = result.get("code_status", -1)
    if code_status == 2:
        if xhs.has_cookie:
            return _ok({"status": "ok", "message": "登录成功,Cookie 已保存"})
        return _ok({"status": "waiting", "code_status": code_status,
                     "message": "已确认但 Cookie 未就绪"})
    status_map = {0: "等待扫码", 1: "已扫码,请在手机上确认"}
    return _ok({
        "status": "waiting",
        "code_status": code_status,
        "message": status_map.get(code_status, f"未知状态: {code_status}"),
    })


# ===== Scrapling 增强爬取工具 =====

@mcp.tool()
@_tool_error_handler
def scrape_note(url_or_id: str, ctx: Context = None) -> str:
    """用隐身浏览器直接爬取小红书笔记页面（API 被封时的备用方案）。

    使用 Scrapling + Patchright 隐身浏览器绕过反爬，直接从网页提取笔记内容。

    Args:
        url_or_id: 笔记链接或笔记 ID
    """
    return _ok(scrape_note_by_url(url_or_id.strip()))


@mcp.tool()
@_tool_error_handler
def scrape_search_notes(keyword: str, page: int = 1,
                        ctx: Context = None) -> str:
    """用隐身浏览器直接搜索小红书（API 被封时的备用方案）。

    使用 Scrapling + Patchright 隐身浏览器绕过反爬，直接从搜索页面提取结果。

    Args:
        keyword: 搜索关键词
        page: 页码,默认 1
    """
    return _ok(scrape_search(
        keyword=validate_keyword(keyword),
        page=clamp(page, 1, 100, 1),
    ))


@mcp.tool()
@_tool_error_handler
def scrape_webpage(url: str, use_browser: bool = False,
                   ctx: Context = None) -> str:
    """通用隐身网页抓取工具。

    使用 Scrapling 的 TLS 指纹伪装（curl_cffi）或隐身浏览器抓取任意网页。

    Args:
        url: 目标网页 URL
        use_browser: 是否使用隐身浏览器（渲染 JS）,默认 False 用 HTTP 请求
    """
    if not url.strip().startswith("http"):
        raise ValueError("URL 必须以 http:// 或 https:// 开头")
    return _ok(fetch_url(url.strip(), use_browser=use_browser))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="小红书 MCP Server")
    parser.add_argument(
        "--transport", choices=["stdio", "sse", "streamable-http"],
        default="stdio", help="传输方式（默认 stdio）",
    )
    parser.add_argument(
        "--port", type=int, default=config.MCP_PORT,
        help=f"HTTP 监听端口（默认 {config.MCP_PORT}，仅 sse/streamable-http 生效）",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="HTTP 监听地址（默认 127.0.0.1）",
    )
    args = parser.parse_args()

    # stdio 模式：仅 WARNING 日志，避免干扰 MCP 协议；HTTP 模式：正常 INFO
    if args.transport == "stdio":
        logging.basicConfig(
            level=logging.WARNING, stream=sys.stderr,
            format="%(levelname)s - %(name)s - %(message)s",
        )
    else:
        logging.basicConfig(
            level=logging.INFO, stream=sys.stderr,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    if args.transport in ("sse", "streamable-http"):
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        logger.info(
            "MCP Server 启动: %s 模式, %s:%d",
            args.transport, args.host, args.port,
        )

    mcp.run(transport=args.transport)
