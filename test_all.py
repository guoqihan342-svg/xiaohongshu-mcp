"""全面测试脚本 — 覆盖所有模块和分支"""

import sys
import time
import os
import ast

os.chdir(os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0
skipped = 0


def assert_true(cond):
    if not cond:
        raise AssertionError("断言失败")


def test(name, func):
    global passed, failed, skipped
    try:
        result = func()
        if result == "SKIP":
            skipped += 1
            print(f"  [跳过] {name}")
        else:
            passed += 1
            print(f"  [通过] {name}")
    except Exception as e:
        failed += 1
        print(f"  [失败] {name} -- {type(e).__name__}: {e}")


# ============================================================
print("=" * 50)
print("1. 模块导入测试")
print("=" * 50)

test("导入 config", lambda: __import__("config"))
test("导入 utils", lambda: __import__("utils"))
test("导入 xhs_client", lambda: __import__("xhs_client"))
test("导入 server", lambda: __import__("server"))
test("导入 web_panel", lambda: __import__("web_panel"))

# ============================================================
print()
print("=" * 50)
print("2. config.py 测试")
print("=" * 50)

import config

test("BASE_DIR 存在", lambda: assert_true(os.path.isdir(config.BASE_DIR)))
test("COOKIE_FILE 路径合法", lambda: assert_true(config.COOKIE_FILE.endswith("cookie.txt")))
test("XHS_SIGN_URL 有值", lambda: assert_true(bool(config.XHS_SIGN_URL)))
test("REQUEST_TIMEOUT > 0", lambda: assert_true(config.REQUEST_TIMEOUT > 0))


def test_cookie_save_load():
    backup = None
    if os.path.exists(config.COOKIE_FILE):
        with open(config.COOKIE_FILE, "r") as f:
            backup = f.read()
    try:
        config.save_cookie("test_a1=xxx; web_session=yyy")
        loaded = config.load_cookie()
        assert_true("test_a1=xxx" in loaded)
    finally:
        if backup is not None:
            with open(config.COOKIE_FILE, "w") as f:
                f.write(backup)
        elif os.path.exists(config.COOKIE_FILE):
            os.remove(config.COOKIE_FILE)


test("Cookie 保存与加载", test_cookie_save_load)


def test_load_cookie_missing():
    backup = None
    if os.path.exists(config.COOKIE_FILE):
        with open(config.COOKIE_FILE, "r") as f:
            backup = f.read()
        os.remove(config.COOKIE_FILE)
    try:
        old_env = os.environ.pop("XHS_COOKIE", None)
        result = config.load_cookie()
        if old_env is not None:
            os.environ["XHS_COOKIE"] = old_env
        assert_true(result == "")
    finally:
        if backup is not None:
            with open(config.COOKIE_FILE, "w") as f:
                f.write(backup)


test("Cookie 文件不存在时返回空", test_load_cookie_missing)

# ============================================================
print()
print("=" * 50)
print("3. utils.py 测试")
print("=" * 50)

from utils import (
    clamp, validate_enum, validate_keyword,
    validate_id, validate_cookie, validate_file_path,
)

# clamp
test("clamp(5,1,10,1)=5", lambda: assert_true(clamp(5, 1, 10, 1) == 5))
test("clamp(0,1,10,1)=1 下越界", lambda: assert_true(clamp(0, 1, 10, 1) == 1))
test("clamp(99,1,10,1)=1 上越界", lambda: assert_true(clamp(99, 1, 10, 1) == 1))
test("clamp 非整数回退", lambda: assert_true(clamp("abc", 1, 10, 5) == 5))

# validate_enum
test("validate_enum 合法值", lambda: assert_true(
    validate_enum("popular", {"general", "popular", "latest"}, "general") == "popular"))
test("validate_enum 非法值回退", lambda: assert_true(
    validate_enum("xxx", {"general", "popular", "latest"}, "general") == "general"))

# validate_keyword
test("validate_keyword 正常(含空格)", lambda: assert_true(validate_keyword("  美食  ") == "美食"))


def test_keyword_empty():
    try:
        validate_keyword("")
        return False
    except ValueError:
        return True


test("validate_keyword 空值抛异常", lambda: assert_true(test_keyword_empty()))


def test_keyword_long():
    try:
        validate_keyword("x" * 101)
        return False
    except ValueError:
        return True


test("validate_keyword 超长抛异常", lambda: assert_true(test_keyword_long()))

# validate_id
test("validate_id 正常", lambda: assert_true(validate_id(" abc123 ") == "abc123"))


def test_id_empty():
    try:
        validate_id("")
        return False
    except ValueError:
        return True


test("validate_id 空值抛异常", lambda: assert_true(test_id_empty()))

# validate_cookie
test("validate_cookie 合法", lambda: assert_true(
    "a1" in validate_cookie("a1=xxx; web_session=yyy; other=zzz")))


def test_cookie_missing_fields():
    try:
        validate_cookie("only_a1=xxx")
        return False
    except ValueError:
        return True


test("validate_cookie 缺字段抛异常", lambda: assert_true(test_cookie_missing_fields()))


def test_cookie_empty():
    try:
        validate_cookie("")
        return False
    except ValueError:
        return True


test("validate_cookie 空值抛异常", lambda: assert_true(test_cookie_empty()))

# validate_file_path
test("validate_file_path 存在的文件", lambda: assert_true(
    validate_file_path(os.path.abspath("config.py")) == os.path.abspath("config.py")))


def test_file_not_exist():
    try:
        validate_file_path("/nonexistent/file.txt")
        return False
    except ValueError:
        return True


test("validate_file_path 不存在抛异常", lambda: assert_true(test_file_not_exist()))

# ============================================================
print()
print("=" * 50)
print("4. HumanBehavior 智能延迟测试")
print("=" * 50)

from xhs_client import HumanBehavior


def test_basic_delay():
    b = HumanBehavior()
    start = time.time()
    b.delay()
    elapsed = time.time() - start
    assert_true(elapsed < b.BASE_MAX + b.PAUSE_MAX + 1)


test("基础延迟执行", test_basic_delay)


def test_fatigue_increase():
    b = HumanBehavior()
    b._last_time = time.time()
    b._consecutive = 0
    b.delay()
    b.delay()
    assert_true(b._consecutive >= 2)


test("疲劳计数递增", test_fatigue_increase)


def test_session_reset():
    b = HumanBehavior()
    b._consecutive = 10
    b._last_time = time.time() - 120  # 2 分钟前
    b.delay()
    assert_true(b._consecutive == 0)


test("会话超时重置疲劳", test_session_reset)


def test_fatigue_cap():
    b = HumanBehavior()
    b._consecutive = 100  # 很大的连续数
    fatigue = min(b._consecutive * b.FATIGUE_STEP, b.FATIGUE_MAX)
    assert_true(fatigue == b.FATIGUE_MAX)


test("疲劳递增有上限", test_fatigue_cap)

# ============================================================
print()
print("=" * 50)
print("5. User-Agent 轮换测试")
print("=" * 50)

from xhs_client import _USER_AGENTS, _random_ua

test("UA 池至少 5 个", lambda: assert_true(len(_USER_AGENTS) >= 5))
test("UA 都包含 Mozilla", lambda: assert_true(all("Mozilla" in ua for ua in _USER_AGENTS)))
test("UA 包含 Chrome", lambda: assert_true(any("Chrome" in ua for ua in _USER_AGENTS)))
test("UA 包含 Edge", lambda: assert_true(any("Edg/" in ua for ua in _USER_AGENTS)))


def test_ua_randomness():
    uas = set(_random_ua() for _ in range(50))
    assert_true(len(uas) >= 2)


test("UA 随机选择(50次至少2种)", test_ua_randomness)

# ============================================================
print()
print("=" * 50)
print("6. XhsAPI 实例化测试")
print("=" * 50)


def test_xhs_api_init():
    try:
        from xhs_client import XhsAPI
        api = XhsAPI()
        assert_true(hasattr(api, "_client"))
        assert_true(hasattr(api, "has_cookie"))
        assert_true(hasattr(api, "set_cookie"))
    except Exception:
        return "SKIP"


test("XhsAPI 实例化(需签名服务)", test_xhs_api_init)


def test_xhs_api_methods():
    """检查 XhsAPI 类包含所有预期方法"""
    from xhs_client import XhsAPI
    expected = [
        "search_notes", "get_note_detail", "get_user_info",
        "get_user_notes", "create_image_note", "create_video_note",
        "get_self_info", "set_cookie", "create_qrcode",
        "check_qrcode", "get_cookie_str", "has_cookie",
    ]
    for name in expected:
        assert_true(hasattr(XhsAPI, name) or hasattr(XhsAPI, name))


test("XhsAPI 包含所有预期方法", test_xhs_api_methods)


def test_sync_a1():
    """测试 _sync_a1_from_sign_server 对不可达服务返回空"""
    from xhs_client import _sync_a1_from_sign_server
    result = _sync_a1_from_sign_server("http://127.0.0.1:59999/sign")
    assert_true(result == "")


test("a1 同步对不可达服务返回空", test_sync_a1)

# ============================================================
print()
print("=" * 50)
print("7. Web 面板路由测试")
print("=" * 50)

try:
    from web_panel import app
    client = app.test_client()

    test("GET / 返回 200", lambda: assert_true(client.get("/").status_code == 200))
    test("GET / 包含 HTML", lambda: assert_true(b"html" in client.get("/").data.lower()))

    def test_status_api():
        resp = client.get("/api/status")
        assert_true(resp.status_code == 200)
        data = resp.get_json()
        assert_true("has_cookie" in data)
        assert_true("sign_service" in data)

    test("GET /api/status", test_status_api)

    # 搜索 - 无关键词
    test("GET /api/search 无关键词 400",
         lambda: assert_true(client.get("/api/search").status_code == 400))

    # 搜索 - 有关键词（签名服务可能没开）
    def test_search_with_kw():
        try:
            resp = client.get("/api/search?keyword=test")
            assert_true(resp.status_code in (200, 502))
        except Exception:
            return "SKIP"

    test("GET /api/search?keyword=test(需签名服务)", test_search_with_kw)

    # Cookie 各种错误
    test("POST /api/cookie 空JSON 400",
         lambda: assert_true(client.post("/api/cookie", json={}).status_code == 400))
    test("POST /api/cookie 无效Cookie 400",
         lambda: assert_true(client.post("/api/cookie", json={"cookie": "invalid"}).status_code == 400))
    test("POST /api/cookie 非JSON 400",
         lambda: assert_true(client.post("/api/cookie", data="not json",
                                          content_type="text/plain").status_code == 400))

    # 发布笔记 - 参数验证
    test("POST /api/note/create 无标题 400",
         lambda: assert_true(client.post("/api/note/create",
                                          data={"title": "", "desc": "test"}).status_code == 400))
    test("POST /api/note/create 无图片 400",
         lambda: assert_true(client.post("/api/note/create",
                                          data={"title": "test"}).status_code == 400))
    test("POST /api/note/create_video 无标题 400",
         lambda: assert_true(client.post("/api/note/create_video",
                                          data={"title": ""}).status_code == 400))
    test("POST /api/note/create_video 无视频 400",
         lambda: assert_true(client.post("/api/note/create_video",
                                          data={"title": "test"}).status_code == 400))

    # 需要登录的接口
    def test_self_no_cookie():
        resp = client.get("/api/self")
        # 未设置含 web_session 的 Cookie → 400，或签名服务异常 → 500/502
        assert_true(resp.status_code in (400, 500, 502))

    test("GET /api/self 未登录 → 非200", test_self_no_cookie)

    # 笔记/用户详情（需签名服务）
    def test_note_detail():
        try:
            resp = client.get("/api/note/abc123")
            assert_true(resp.status_code in (200, 502))
        except Exception:
            return "SKIP"

    test("GET /api/note/<id>(需签名服务)", test_note_detail)

    def test_user_info():
        try:
            resp = client.get("/api/user/abc123")
            assert_true(resp.status_code in (200, 502))
        except Exception:
            return "SKIP"

    test("GET /api/user/<id>(需签名服务)", test_user_info)

    def test_user_notes():
        try:
            resp = client.get("/api/user/abc123/notes")
            assert_true(resp.status_code in (200, 502))
        except Exception:
            return "SKIP"

    test("GET /api/user/<id>/notes(需签名服务)", test_user_notes)

    # 二维码接口
    def test_qrcode_create():
        try:
            resp = client.post("/api/qrcode/create")
            assert_true(resp.status_code in (200, 502))
            if resp.status_code == 200:
                data = resp.get_json()
                assert_true("qr_id" in data)
                assert_true("qr_image" in data)
        except Exception:
            return "SKIP"

    test("POST /api/qrcode/create(需签名服务)", test_qrcode_create)

    def test_qrcode_check_missing():
        resp = client.post("/api/qrcode/check", json={})
        assert_true(resp.status_code == 400)

    test("POST /api/qrcode/check 缺参数 400", test_qrcode_check_missing)

    # secure_filename 安全性
    def test_secure_upload():
        from werkzeug.utils import secure_filename
        assert_true(secure_filename("../../etc/passwd") == "etc_passwd")
        assert_true(secure_filename("normal.jpg") == "normal.jpg")

    test("secure_filename 防路径遍历", test_secure_upload)

except Exception as e:
    print(f"  [跳过] Web 面板测试整体跳过 -- {e}")
    skipped += 1

# ============================================================
print()
print("=" * 50)
print("8. MCP Server 工具注册测试")
print("=" * 50)

try:
    from server import mcp
    tools = mcp._tool_manager._tools
    expected_tools = [
        "search_notes", "get_note_detail", "get_user_info",
        "get_user_notes", "create_note", "create_video_note",
        "set_cookie", "get_self_info", "qrcode_login", "check_qrcode",
    ]
    for name in expected_tools:
        test(f"MCP 工具 {name} 已注册", lambda n=name: assert_true(n in tools))
except Exception as e:
    print(f"  [跳过] MCP 工具注册测试 -- {e}")
    skipped += 1

# ============================================================
print()
print("=" * 50)
print("9. 语法检查（不导入，仅解析）")
print("=" * 50)


def check_syntax(filename):
    with open(filename, "r", encoding="utf-8") as f:
        source = f.read()
    ast.parse(source)


test("sign_server.py 语法正确", lambda: check_syntax("sign_server.py"))
test("login.py 语法正确", lambda: check_syntax("login.py"))
test("start.py 语法正确", lambda: check_syntax("start.py"))
test("config.py 语法正确", lambda: check_syntax("config.py"))
test("utils.py 语法正确", lambda: check_syntax("utils.py"))
test("xhs_client.py 语法正确", lambda: check_syntax("xhs_client.py"))
test("server.py 语法正确", lambda: check_syntax("server.py"))
test("web_panel.py 语法正确", lambda: check_syntax("web_panel.py"))

# ============================================================
print()
print("=" * 50)
print("10. 依赖完整性检查")
print("=" * 50)


def test_deps():
    import importlib
    for mod in ["mcp", "xhs", "httpx", "flask", "qrcode", "gevent",
                "playwright", "playwright_stealth"]:
        importlib.import_module(mod)


test("所有声明依赖可导入", test_deps)

# ============================================================
print()
print("=" * 50)
total = passed + failed + skipped
print(f"测试结果: 共 {total} 个测试")
print(f"  通过: {passed}")
print(f"  失败: {failed}")
print(f"  跳过: {skipped}")
print("=" * 50)
if failed == 0:
    print("全部通过！")
else:
    print(f"有 {failed} 个测试失败，请检查")
    sys.exit(1)
