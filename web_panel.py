"""小红书 Web 管理面板"""

import logging
import os
import tempfile
import functools

import httpx
from flask import Flask, jsonify, request, render_template
from xhs.exception import DataFetchError, IPBlockError, SignError, NeedVerifyError

from xhs_client import XhsAPI
from utils import validate_keyword, validate_cookie, clamp, validate_enum
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
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
        except SignError:
            return jsonify({"error": "签名失败", "message": "请检查签名服务是否正常运行"}), 502
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
            p = os.path.join(UPLOAD_DIR, f.filename)
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
    vpath = os.path.join(UPLOAD_DIR, video.filename)
    cpath = None
    try:
        video.save(vpath)
        cover = request.files.get("cover")
        if cover:
            cpath = os.path.join(UPLOAD_DIR, cover.filename)
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


if __name__ == "__main__":
    logger.info("Web 管理面板: http://127.0.0.1:8080")
    app.run(host="127.0.0.1", port=8080, debug=False)
