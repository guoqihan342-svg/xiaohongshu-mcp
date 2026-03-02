"""小红书 Web 管理面板"""

import base64
import io
import logging
import os
import tempfile
import functools

import httpx
import qrcode
from flask import Flask, jsonify, request, render_template
from werkzeug.utils import secure_filename
from xhs.exception import DataFetchError, IPBlockError, SignError, NeedVerifyError

from xhs_client import XhsAPI
from scraper import scrape_note_by_url, scrape_search, fetch_url
from utils import validate_keyword, validate_cookie, clamp, validate_enum
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder=os.path.join(config.BASE_DIR, "templates"),
)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

xhs = XhsAPI()

UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "xhs_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def api_handler(func):
    """API 统一异常处理"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            return jsonify({"error": "参数错误", "message": str(e)}), 400
        except IPBlockError:
            return jsonify({"error": "IP 被限流", "message": "请求过于频繁，请稍后再试"}), 429
        except SignError as e:
            return jsonify({"error": "签名失败", "message": str(e) or "请检查签名服务是否正常运行"}), 502
        except NeedVerifyError:
            return jsonify({"error": "需要验证码", "message": "触发了人机验证，请稍后再试"}), 403
        except DataFetchError as e:
            return jsonify({"error": "数据获取失败", "message": str(e)}), 502
        except RuntimeError as e:
            return jsonify({"error": "操作失败", "message": str(e)}), 400
        except Exception as e:
            logger.exception("API 异常")
            return jsonify({"error": "未知错误", "message": f"{type(e).__name__}: {e}"}), 500
    return wrapper


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
@api_handler
def api_status():
    sign_ok = False
    try:
        httpx.post(config.XHS_SIGN_URL,
                   json={"uri": "/test", "data": "", "a1": "", "web_session": ""},
                   timeout=3)
        sign_ok = True
    except Exception:
        pass
    return jsonify({"has_cookie": xhs.has_cookie, "sign_service": sign_ok})


@app.route("/api/cookie", methods=["POST"])
@api_handler
def api_set_cookie():
    data = request.get_json(silent=True)
    if not data or "cookie" not in data:
        raise ValueError("请提供 cookie 字段")
    xhs.set_cookie(validate_cookie(data["cookie"]))
    return jsonify({"message": "Cookie 设置成功"})


@app.route("/api/self")
@api_handler
def api_self_info():
    return jsonify(xhs.get_self_info())


@app.route("/api/search")
@api_handler
def api_search():
    keyword = validate_keyword(request.args.get("keyword", ""))
    page = clamp(int(request.args.get("page", 1)), 1, 100, 1)
    page_size = clamp(int(request.args.get("page_size", 20)), 1, 50, 20)
    sort = validate_enum(request.args.get("sort", "general"),
                         {"general", "popular", "latest"}, "general")
    note_type = validate_enum(request.args.get("note_type", "all"),
                              {"all", "video", "image"}, "all")
    return jsonify(xhs.search_notes(
        keyword=keyword, page=page, page_size=page_size,
        sort=sort, note_type=note_type))


@app.route("/api/note/<note_id>")
@api_handler
def api_note_detail(note_id):
    return jsonify(xhs.get_note_detail(note_id=note_id))


@app.route("/api/user/<user_id>")
@api_handler
def api_user_info(user_id):
    return jsonify(xhs.get_user_info(user_id=user_id))


@app.route("/api/user/<user_id>/notes")
@api_handler
def api_user_notes(user_id):
    return jsonify(xhs.get_user_notes(
        user_id=user_id, cursor=request.args.get("cursor", "")))


@app.route("/api/note/create", methods=["POST"])
@api_handler
def api_create_note():
    title = request.form.get("title", "").strip()
    if not title:
        raise ValueError("笔记标题不能为空")
    files = request.files.getlist("images")
    if not files:
        raise ValueError("至少需要一张图片")
    paths = []
    try:
        for f in files:
            p = os.path.join(UPLOAD_DIR, secure_filename(f.filename))
            f.save(p)
            paths.append(p)
        return jsonify(xhs.create_image_note(
            title=title, desc=request.form.get("desc", ""),
            image_paths=paths,
            is_private=request.form.get("is_private", "false").lower() == "true"))
    finally:
        for p in paths:
            try: os.remove(p)
            except OSError: pass


@app.route("/api/note/create_video", methods=["POST"])
@api_handler
def api_create_video():
    title = request.form.get("title", "").strip()
    if not title:
        raise ValueError("笔记标题不能为空")
    video = request.files.get("video")
    if not video:
        raise ValueError("请上传视频文件")
    vpath = os.path.join(UPLOAD_DIR, secure_filename(video.filename))
    cpath = None
    try:
        video.save(vpath)
        cover = request.files.get("cover")
        if cover:
            cpath = os.path.join(UPLOAD_DIR, secure_filename(cover.filename))
            cover.save(cpath)
        return jsonify(xhs.create_video_note(
            title=title, desc=request.form.get("desc", ""),
            video_path=vpath, cover_path=cpath,
            is_private=request.form.get("is_private", "false").lower() == "true"))
    finally:
        try: os.remove(vpath)
        except OSError: pass
        if cpath:
            try: os.remove(cpath)
            except OSError: pass


@app.route("/api/refresh-sign", methods=["POST"])
@api_handler
def api_refresh_sign():
    """重建签名服务浏览器会话并同步新 a1"""
    refresh_url = config.XHS_SIGN_URL.rsplit("/", 1)[0] + "/refresh"
    resp = httpx.post(refresh_url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "重建失败"))
    # 同步新 a1
    a1 = data.get("a1", "")
    if a1:
        cookie_dict = xhs._client.cookie_dict
        old_a1 = cookie_dict.get("a1", "")
        cookie_dict["a1"] = a1
        if old_a1 and old_a1 != a1 and "web_session" in cookie_dict:
            del cookie_dict["web_session"]
        xhs._client.cookie = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
    return jsonify({"message": "签名服务已刷新，请重新扫码登录" if a1 else "签名服务已刷新"})


@app.route("/api/qrcode/create", methods=["POST"])
@api_handler
def api_qrcode_create():
    """生成扫码登录二维码"""
    result = xhs.create_qrcode()
    qr_url = result.get("url", "")
    if not qr_url:
        raise RuntimeError("获取二维码链接失败")
    # 生成二维码图片 → base64
    img = qrcode.make(qr_url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({
        "qr_id": result.get("qr_id", ""),
        "code": result.get("code", ""),
        "qr_image": f"data:image/png;base64,{b64}",
    })


@app.route("/api/qrcode/check", methods=["POST"])
@api_handler
def api_qrcode_check():
    """轮询检查二维码扫描状态"""
    data = request.get_json(silent=True)
    if not data or "qr_id" not in data or "code" not in data:
        raise ValueError("缺少 qr_id 或 code 参数")
    # xhs_client.check_qrcode 会自动激活会话并保存 Cookie
    result = xhs.check_qrcode(qr_id=data["qr_id"], code=data["code"])
    code_status = result.get("code_status", -1)
    # code_status: 0=未扫描, 1=已扫描待确认, 2=已确认登录
    if code_status == 2:
        if xhs.has_cookie:
            return jsonify({"status": "ok", "message": "登录成功"})
        else:
            return jsonify({"status": "waiting", "code_status": code_status,
                            "message": "已确认但 Cookie 未就绪，请稍等"})
    status_map = {0: "等待扫码", 1: "已扫码，请在手机上确认"}
    return jsonify({
        "status": "waiting",
        "code_status": code_status,
        "message": status_map.get(code_status, f"未知状态: {code_status}"),
    })


# ===== Scrapling 增强爬取 API =====

@app.route("/api/scrape/note", methods=["POST"])
@api_handler
def api_scrape_note():
    """用隐身浏览器直接爬取笔记页面（API 被封时的备用方案）"""
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        raise ValueError("请提供 url 字段（笔记链接或 ID）")
    return jsonify(scrape_note_by_url(data["url"].strip()))


@app.route("/api/scrape/search")
@api_handler
def api_scrape_search():
    """用隐身浏览器直接搜索（API 被封时的备用方案）"""
    keyword = validate_keyword(request.args.get("keyword", ""))
    page = clamp(int(request.args.get("page", 1)), 1, 100, 1)
    return jsonify(scrape_search(keyword=keyword, page=page))


@app.route("/api/scrape/url", methods=["POST"])
@api_handler
def api_scrape_url():
    """通用隐身网页抓取"""
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        raise ValueError("请提供 url 字段")
    url = data["url"].strip()
    if not url.startswith("http"):
        raise ValueError("URL 必须以 http:// 或 https:// 开头")
    use_browser = data.get("use_browser", False)
    return jsonify(fetch_url(url, use_browser=use_browser))


if __name__ == "__main__":
    logger.info("Web 管理面板: http://127.0.0.1:8080")
    app.run(host="127.0.0.1", port=8080, debug=False)
