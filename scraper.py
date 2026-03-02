"""Scrapling 增强爬取模块 — 当 API 被封时的备用方案

使用 curl_cffi TLS 指纹伪装 + Patchright 隐身浏览器，
直接从小红书网页抓取笔记内容、搜索结果等。
"""

import logging
import re
import json

from scrapling import Fetcher, StealthyFetcher

logger = logging.getLogger(__name__)


def _extract_json_from_script(html: str, pattern: str) -> dict | None:
    """从页面 <script> 标签中提取 JSON 数据"""
    match = re.search(pattern, html, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, IndexError):
            pass
    return None


def scrape_note_by_url(url: str) -> dict:
    """用隐身浏览器直接爬取小红书笔记页面

    当 API 返回 300011/300015 等错误时，可作为备用方案。
    通过 StealthyFetcher（Patchright 隐身浏览器）渲染页面并提取数据。

    Args:
        url: 笔记链接，如 https://www.xiaohongshu.com/explore/xxx
             或 https://www.xiaohongshu.com/discovery/item/xxx

    Returns:
        包含 title, desc, images, author, likes 等字段的字典
    """
    if not url.startswith("http"):
        url = f"https://www.xiaohongshu.com/explore/{url}"

    logger.info("隐身浏览器爬取: %s", url)
    response = StealthyFetcher.fetch(
        url,
        headless=True,
        network_idle=True,
        block_webrtc=True,
        hide_canvas=True,
    )

    result = {"url": url, "status_code": response.status}

    # 方式1: 从 SSR 数据中提取（window.__INITIAL_STATE__）
    state = _extract_json_from_script(
        response.text, r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*</script>'
    )
    if state:
        note_data = state.get("note", {}).get("noteDetailMap", {})
        if note_data:
            first_key = next(iter(note_data), None)
            if first_key:
                detail = note_data[first_key].get("note", {})
                result.update({
                    "title": detail.get("title", ""),
                    "desc": detail.get("desc", ""),
                    "type": detail.get("type", ""),
                    "author": {
                        "nickname": detail.get("user", {}).get("nickname", ""),
                        "user_id": detail.get("user", {}).get("userId", ""),
                    },
                    "likes": detail.get("interactInfo", {}).get("likedCount", ""),
                    "collects": detail.get("interactInfo", {}).get("collectedCount", ""),
                    "comments": detail.get("interactInfo", {}).get("commentCount", ""),
                    "images": [
                        img.get("urlDefault", "") or img.get("url", "")
                        for img in detail.get("imageList", [])
                    ],
                    "source": "scrapling_ssr",
                })
                return result

    # 方式2: 从 DOM 中提取
    title_el = response.css("#detail-title")
    desc_el = response.css("#detail-desc")
    author_el = response.css(".author-wrapper .username")
    images = response.css(".note-image-list img")

    result.update({
        "title": title_el.get().text if title_el else "",
        "desc": desc_el.get().text if desc_el else "",
        "author": {"nickname": author_el.get().text if author_el else ""},
        "images": [img.attrib.get("src", "") for img in (images or [])],
        "source": "scrapling_dom",
    })
    return result


def scrape_search(keyword: str, page: int = 1) -> dict:
    """用隐身浏览器直接搜索小红书

    当搜索 API 被封时的备用方案。直接访问搜索页面并提取结果。

    Args:
        keyword: 搜索关键词
        page: 页码

    Returns:
        包含 items 列表的字典
    """
    url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&page={page}"
    logger.info("隐身浏览器搜索: %s (第%d页)", keyword, page)

    response = StealthyFetcher.fetch(
        url,
        headless=True,
        network_idle=True,
        block_webrtc=True,
        hide_canvas=True,
    )

    result = {"keyword": keyword, "page": page, "items": []}

    # 从 SSR 数据提取
    state = _extract_json_from_script(
        response.text, r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*</script>'
    )
    if state:
        feeds = state.get("search", {}).get("feeds", [])
        if not feeds:
            feeds = state.get("feed", {}).get("feeds", [])
        for feed in feeds:
            note = feed.get("note_card", feed)
            result["items"].append({
                "note_id": feed.get("id", ""),
                "title": note.get("display_title", note.get("title", "")),
                "author": note.get("user", {}).get("nickname", ""),
                "cover": note.get("cover", {}).get("url", ""),
                "likes": note.get("interact_info", {}).get("liked_count", ""),
                "type": note.get("type", ""),
            })
        result["source"] = "scrapling_ssr"
        return result

    # DOM 降级提取
    cards = response.css("section.note-item")
    for card in (cards or []):
        title_el = card.css(".title")
        author_el = card.css(".author .name")
        cover_el = card.css("img")
        result["items"].append({
            "title": title_el.get().text if title_el else "",
            "author": author_el.get().text if author_el else "",
            "cover": cover_el.get().attrib.get("src", "") if cover_el else "",
        })
    result["source"] = "scrapling_dom"
    return result


def fetch_url(url: str, use_browser: bool = False) -> dict:
    """通用隐身网页抓取

    Args:
        url: 目标 URL
        use_browser: True 用隐身浏览器（渲染 JS），False 用 TLS 指纹伪装 HTTP

    Returns:
        包含 status, html, text 等字段的字典
    """
    logger.info("抓取 URL: %s (浏览器=%s)", url, use_browser)

    if use_browser:
        response = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            block_webrtc=True,
        )
    else:
        response = Fetcher.get(
            url,
            stealthy_headers=True,
            follow_redirects=True,
        )

    return {
        "url": url,
        "status": response.status,
        "title": (response.css("title").get().text
                  if response.css("title") else ""),
        "text_length": len(response.text),
        "source": "scrapling_browser" if use_browser else "scrapling_http",
    }
