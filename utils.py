"""共享工具函数 — 参数验证"""

import os


def clamp(value: int, min_val: int, max_val: int, default: int) -> int:
    """将整数值限制在 [min_val, max_val] 范围内"""
    if not isinstance(value, int) or value < min_val or value > max_val:
        return default
    return value


def validate_enum(value: str, allowed: set[str], default: str) -> str:
    """验证字符串是否在允许的枚举值中"""
    return value if value in allowed else default


def validate_keyword(keyword: str) -> str:
    """验证搜索关键词"""
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("搜索关键词不能为空")
    if len(keyword) > 100:
        raise ValueError("搜索关键词过长（最多 100 个字符）")
    return keyword


def validate_id(value: str, name: str = "ID") -> str:
    """验证 ID（非空字符串）"""
    value = value.strip()
    if not value:
        raise ValueError(f"{name} 不能为空")
    return value


def validate_cookie(cookie: str) -> str:
    """基本的 Cookie 格式验证"""
    cookie = cookie.strip()
    if not cookie:
        raise ValueError("Cookie 不能为空")
    if "a1" not in cookie or "web_session" not in cookie:
        raise ValueError("Cookie 需包含 a1 和 web_session 字段，"
                         "请从浏览器开发者工具中完整复制。")
    return cookie


def validate_file_path(path: str, name: str = "文件") -> str:
    """验证文件路径是否存在"""
    if not os.path.isfile(path):
        raise ValueError(f"{name}不存在: {path}")
    return path
