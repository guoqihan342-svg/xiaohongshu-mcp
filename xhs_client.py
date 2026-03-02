"""小红书 API 客户端封装"""

import atexit
import logging
import random
import threading
import time
import httpx
from xhs import XhsClient, SearchSortType, SearchNoteType

import config

logger = logging.getLogger(__name__)


# ===== 智能延迟系统 =====
# 模拟真人浏览会话：连续操作时间隔逐渐增大（疲劳效应），长时间空闲后重置

class HumanBehavior:
    """模拟人类浏览行为的延迟控制器"""

    # 基础间隔范围（秒）
    BASE_MIN = 1.0
    BASE_MAX = 3.0
    # 连续请求时，每次额外增加的延迟范围
    FATIGUE_STEP = 0.3
    FATIGUE_MAX = 2.5
    # 如果空闲超过此时间（秒），视为新会话，重置疲劳
    SESSION_RESET = 60.0
    # 偶尔模拟"发呆"的概率和时长
    PAUSE_CHANCE = 0.08
    PAUSE_MIN = 5.0
    PAUSE_MAX = 12.0

    def __init__(self):
        self._last_time = 0.0
        self._consecutive = 0
        self._lock = threading.Lock()

    def delay(self):
        """根据会话状态计算并执行延迟（线程安全）"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_time

            # 长时间空闲 → 新会话，重置疲劳计数
            if elapsed > self.SESSION_RESET:
                self._consecutive = 0
            else:
                self._consecutive += 1

            # 基础延迟 + 疲劳递增（有上限）
            fatigue = min(self._consecutive * self.FATIGUE_STEP, self.FATIGUE_MAX)
            delay = random.uniform(self.BASE_MIN + fatigue, self.BASE_MAX + fatigue)

            # 小概率"发呆"：模拟真人被其他事情打断
            if random.random() < self.PAUSE_CHANCE:
                delay += random.uniform(self.PAUSE_MIN, self.PAUSE_MAX)
                logger.debug("模拟用户暂停 %.1f 秒", delay)

            # 扣除已经过去的时间
            wait = delay - elapsed
            if wait > 0:
                time.sleep(wait)

            self._last_time = time.time()


_behavior = HumanBehavior()


def _human_delay():
    """模拟人类操作的智能延迟"""
    _behavior.delay()


# ===== 随机 User-Agent =====
# 真实浏览器 UA 池，每次创建客户端随机选一个

_USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
]


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)

# 排序方式映射
SORT_MAP = {
    "general": SearchSortType.GENERAL,
    "popular": SearchSortType.MOST_POPULAR,
    "latest": SearchSortType.LATEST,
}

# 笔记类型映射
NOTE_TYPE_MAP = {
    "all": SearchNoteType.ALL,
    "video": SearchNoteType.VIDEO,
    "image": SearchNoteType.IMAGE,
}


def _create_sign_function(sign_url: str):
    """创建签名函数，通过 HTTP 调用签名服务（复用连接，带重试）"""
    client = httpx.Client(timeout=config.REQUEST_TIMEOUT)
    atexit.register(client.close)

    _MAX_RETRIES = 3
    _RETRY_BACKOFF = [1.0, 2.0, 4.0]

    def sign(uri: str, data=None, a1: str = "", web_session: str = ""):
        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = client.post(sign_url, json={
                    "uri": uri,
                    "data": data,
                    "a1": a1,
                    "web_session": web_session,
                })
                resp.raise_for_status()
                result = resp.json()
                if "x-s" not in result or "x-t" not in result:
                    raise ValueError(f"签名服务返回格式异常: {result}")
                return result
            except Exception as e:
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF[attempt]
                    logger.warning(
                        "签名请求失败 (第%d/%d次), %.1f秒后重试: %s",
                        attempt + 1, _MAX_RETRIES, wait, e,
                    )
                    time.sleep(wait)
        raise last_error

    return sign


def _sync_a1_from_sign_server(sign_url: str) -> str:
    """从签名服务获取浏览器的 a1 值，确保签名一致"""
    a1_url = sign_url.rsplit("/", 1)[0] + "/a1"
    try:
        resp = httpx.get(a1_url, timeout=5)
        if resp.status_code == 200:
            a1 = resp.json().get("a1", "")
            if a1:
                logger.info("已从签名服务同步 a1: %s...", a1[:16])
                return a1
    except Exception as e:
        logger.warning("无法从签名服务获取 a1: %s", e)
    return ""


class XhsAPI:
    """小红书 API 客户端封装"""

    def __init__(self):
        sign_fn = _create_sign_function(config.XHS_SIGN_URL)
        ua = _random_ua()
        logger.info("使用 User-Agent: %s", ua[:50] + "...")
        # 构建初始 Cookie：优先用户 Cookie，否则同步签名服务的 a1
        init_cookie = config.XHS_COOKIE or None
        self._client = XhsClient(
            cookie=init_cookie,
            sign=sign_fn,
            timeout=config.REQUEST_TIMEOUT,
            user_agent=ua,
        )
        # 始终同步签名服务的 a1（签名基于签名服务浏览器的 a1 生成）
        a1 = _sync_a1_from_sign_server(config.XHS_SIGN_URL)
        if a1:
            cookie_dict = self._client.cookie_dict
            old_a1 = cookie_dict.get("a1", "")
            cookie_dict["a1"] = a1
            # 如果 a1 变了且有 web_session，该 session 已失效
            if old_a1 and old_a1 != a1 and "web_session" in cookie_dict:
                logger.warning("签名服务 a1 与 Cookie 不匹配，登录态已失效，需重新扫码")
                del cookie_dict["web_session"]
            self._client.cookie = "; ".join(
                f"{k}={v}" for k, v in cookie_dict.items()
            )

    @property
    def has_cookie(self) -> bool:
        """是否已设置用户 Cookie（登录模式），需包含 web_session"""
        cookie = self._client.cookie or ""
        return "web_session" in cookie

    def set_cookie(self, cookie: str):
        """运行时更新 Cookie 并持久化"""
        self._client.cookie = cookie
        config.save_cookie(cookie)

    def search_notes(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        sort: str = "general",
        note_type: str = "all",
    ) -> dict:
        """搜索笔记"""
        _human_delay()
        sort_type = SORT_MAP.get(sort, SearchSortType.GENERAL)
        nt = NOTE_TYPE_MAP.get(note_type, SearchNoteType.ALL)
        return self._client.get_note_by_keyword(
            keyword=keyword,
            page=page,
            page_size=page_size,
            sort=sort_type,
            note_type=nt,
        )

    def get_note_detail(self, note_id: str) -> dict:
        """获取笔记详情"""
        _human_delay()
        return self._client.get_note_by_id(note_id=note_id)

    def get_user_info(self, user_id: str) -> dict:
        """获取用户信息"""
        _human_delay()
        return self._client.get_user_info(user_id=user_id)

    def get_user_notes(self, user_id: str, cursor: str = "") -> dict:
        """获取用户笔记列表"""
        _human_delay()
        return self._client.get_user_notes(user_id=user_id, cursor=cursor)

    def create_image_note(
        self,
        title: str,
        desc: str,
        image_paths: list[str],
        is_private: bool = False,
    ) -> dict:
        """创建图文笔记（需要 Cookie 登录）"""
        if not self.has_cookie:
            raise RuntimeError("创建笔记需要先设置 Cookie 登录")
        return self._client.create_image_note(
            title=title,
            desc=desc,
            files=image_paths,
            is_private=is_private,
        )

    def create_video_note(
        self,
        title: str,
        desc: str,
        video_path: str,
        cover_path: str | None = None,
        is_private: bool = False,
    ) -> dict:
        """创建视频笔记（需要 Cookie 登录）"""
        if not self.has_cookie:
            raise RuntimeError("创建笔记需要先设置 Cookie 登录")
        return self._client.create_video_note(
            title=title,
            video_path=video_path,
            desc=desc,
            cover_path=cover_path,
            is_private=is_private,
        )

    def get_self_info(self) -> dict:
        """获取当前登录用户信息（需要 Cookie 登录）"""
        if not self.has_cookie:
            raise RuntimeError("获取自身信息需要先设置 Cookie 登录")
        return self._client.get_self_info()

    def create_qrcode(self) -> dict:
        """创建扫码登录二维码，返回 qr_id、code、url"""
        return self._client.get_qrcode()

    def check_qrcode(self, qr_id: str, code: str) -> dict:
        """检查二维码扫描状态，登录成功后自动激活并保存 Cookie"""
        result = self._client.check_qrcode(qr_id=qr_id, code=code)
        code_status = result.get("code_status", -1)
        if code_status == 2:
            # 登录成功，激活会话
            try:
                self._client.activate()
                logger.info("登录会话已激活")
            except Exception as e:
                logger.warning("激活会话失败（可忽略）: %s", e)
            # 读取并保存 Cookie（session 中已包含 web_session）
            cookie_str = self._client.cookie or ""
            if cookie_str and "web_session" in cookie_str:
                config.save_cookie(cookie_str)
                logger.info("扫码登录成功，Cookie 已保存")
        return result

    def get_cookie_str(self) -> str:
        """获取当前客户端的完整 Cookie 字符串"""
        return self._client.cookie or ""
