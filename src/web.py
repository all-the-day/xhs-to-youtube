"""
Web 控制台
"""

from __future__ import annotations

import json
import secrets
import traceback
from typing import Any

from flask import Flask, Response, render_template, request, session

from src.config import CONFIG_FILE, COOKIES_FILE, TOKEN_FILE, UPLOADED_FILE, VIDEO_LIST_FILE, load_web_config
from src.core import XHSToYouTube
from src.schedule import get_today_schedule_status, run_scheduled_upload


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    web_config = load_web_config()
    auth_enabled = bool(web_config.get("enabled")) and bool(web_config.get("username")) and bool(web_config.get("password"))
    csrf_enabled = bool(web_config.get("csrf_enabled"))
    if web_config.get("enabled") and not auth_enabled:
        raise ValueError("web.enabled=true requires non-empty web.username and web.password")
    app.secret_key = web_config.get("secret_key") or secrets.token_hex(32)
    app.config["WEB_AUTH_ENABLED"] = auth_enabled
    app.config["WEB_AUTH_USERNAME"] = web_config.get("username", "")
    app.config["WEB_AUTH_PASSWORD"] = web_config.get("password", "")
    app.config["WEB_AUTH_REALM"] = web_config.get("realm", "xhs-to-youtube web console")
    app.config["WEB_CSRF_ENABLED"] = csrf_enabled

    @app.before_request
    def protect_console():
        if app.config["WEB_AUTH_ENABLED"]:
            auth = request.authorization
            if not (
                auth
                and auth.username == app.config["WEB_AUTH_USERNAME"]
                and auth.password == app.config["WEB_AUTH_PASSWORD"]
            ):
                return Response(
                    "Authentication required",
                    401,
                    {"WWW-Authenticate": f'Basic realm="{app.config["WEB_AUTH_REALM"]}", charset="UTF-8"'},
                )

        if request.method == "POST" and app.config["WEB_CSRF_ENABLED"]:
            return _reject_if_csrf_invalid()

        return None

    @app.get("/")
    def index():
        return _render_dashboard()

    @app.post("/transfer")
    def transfer():
        form_data = request.form.to_dict()
        tags_raw = form_data.get("tags", "")
        tags = [item.strip() for item in tags_raw.split(",") if item.strip()]
        logs: list[str] = []
        tool = XHSToYouTube(log_callback=logs.append)

        try:
            result = tool.transfer(
                xhs_url=form_data["url"],
                english_title=form_data.get("title_en") or None,
                custom_desc=form_data.get("desc") or None,
                tags=tags or None,
                privacy=form_data.get("privacy", "public"),
                keep_video=bool(form_data.get("keep_video")),
                translate=bool(form_data.get("translate")),
                translate_title=bool(form_data.get("translate")) or bool(form_data.get("translate_title")),
                translate_desc=bool(form_data.get("translate")) or bool(form_data.get("translate_desc")),
                show_time_suggestion=False,
            )
            return _render_dashboard(
                action_result=_success_result("单视频搬运", "视频已提交到 YouTube。", result, logs),
                form_defaults={"transfer": form_data},
            )
        except Exception as exc:
            return _render_dashboard(
                action_result=_error_result("单视频搬运", exc, logs),
                form_defaults={"transfer": form_data},
            )

    @app.post("/fetch")
    def fetch():
        form_data = request.form.to_dict()
        logs: list[str] = []
        tool = XHSToYouTube(log_callback=logs.append)
        output_file = form_data.get("output") or str(VIDEO_LIST_FILE)

        try:
            result = tool.fetch_user_videos(
                user_url=form_data["url"],
                output_file=output_file,
                page_size=int(form_data.get("page_size", 10)),
            )
            summary = f"已抓取 {result.get('total_count', 0)} 个视频。"
            return _render_dashboard(
                action_result=_success_result("抓取用户视频列表", summary, result, logs),
                form_defaults={"fetch": form_data},
            )
        except Exception as exc:
            return _render_dashboard(
                action_result=_error_result("抓取用户视频列表", exc, logs),
                form_defaults={"fetch": form_data},
            )

    @app.post("/batch")
    def batch():
        form_data = request.form.to_dict()
        logs: list[str] = []
        tool = XHSToYouTube(log_callback=logs.append)
        no_translate = bool(form_data.get("no_translate"))
        translate = (bool(form_data.get("translate_title")) or bool(form_data.get("translate_desc"))) and not no_translate
        translate_title = False if no_translate else (translate or bool(form_data.get("translate_title")))
        translate_desc = False if no_translate else (translate or bool(form_data.get("translate_desc")))

        try:
            result = tool.batch_transfer(
                video_list_path=form_data.get("input") or None,
                interval_min=int(form_data.get("interval_min", 10)),
                interval_max=int(form_data.get("interval_max", 30)),
                privacy=form_data.get("privacy", "public"),
                keep_video=bool(form_data.get("keep_video")),
                skip_uploaded=not bool(form_data.get("force")),
                translate=translate,
                translate_title=translate_title,
                translate_desc=translate_desc,
                limit=int(form_data.get("limit", 0)),
                show_time_suggestion=False,
            )
            summary = (
                f"成功 {result.get('success_count', 0)}，"
                f"跳过 {result.get('skipped', 0)}，"
                f"失败 {result.get('failed', 0)}。"
            )
            return _render_dashboard(
                action_result=_success_result("批量搬运", summary, result, logs),
                form_defaults={"batch": form_data},
            )
        except Exception as exc:
            return _render_dashboard(
                action_result=_error_result("批量搬运", exc, logs),
                form_defaults={"batch": form_data},
            )

    @app.post("/cookie")
    def update_cookie():
        form_data = request.form.to_dict()
        logs: list[str] = []
        tool = XHSToYouTube(log_callback=logs.append)

        content = form_data.get("cookie_content", "").strip()
        if not content:
            return _render_dashboard(
                action_result={
                    "title": "更新 Cookie",
                    "success": False,
                    "summary": "Cookie 内容不能为空。",
                    "data": None,
                    "data_pretty": "",
                    "logs": logs,
                },
                form_defaults={"cookie": form_data},
            )

        try:
            success = tool.update_cookie(content)
            payload = {"cookie_path": str(COOKIES_FILE), "updated": success}
            return _render_dashboard(
                action_result={
                    "title": "更新 Cookie",
                    "success": success,
                    "summary": "Cookie 已更新。" if success else "Cookie 更新失败。",
                    "data": payload,
                    "data_pretty": _format_data(payload),
                    "logs": logs,
                },
                form_defaults={"cookie": {"cookie_content": ""}},
            )
        except Exception as exc:
            return _render_dashboard(
                action_result=_error_result("更新 Cookie", exc, logs),
                form_defaults={"cookie": form_data},
            )

    @app.post("/auth/url")
    def auth_url():
        logs: list[str] = []
        tool = XHSToYouTube(log_callback=logs.append)

        try:
            success, payload = tool.get_authorization_url()
            result = {
                "authorization_url": payload if success else None,
                "message": None if success else payload,
            }
            summary = "已生成 YouTube 授权链接。" if success else f"生成失败：{payload}"
            return _render_dashboard(
                action_result={
                    "title": "生成 YouTube 授权链接",
                    "success": success,
                    "summary": summary,
                    "data": result,
                    "data_pretty": _format_data(result),
                    "logs": logs,
                },
            )
        except Exception as exc:
            return _render_dashboard(action_result=_error_result("生成 YouTube 授权链接", exc, logs))

    @app.post("/auth/code")
    def auth_code():
        form_data = request.form.to_dict()
        logs: list[str] = []
        tool = XHSToYouTube(log_callback=logs.append)
        code = form_data.get("code", "").strip()

        if not code:
            return _render_dashboard(
                action_result={
                    "title": "提交 YouTube 授权码",
                    "success": False,
                    "summary": "授权码不能为空。",
                    "data": None,
                    "data_pretty": "",
                    "logs": logs,
                },
                form_defaults={"auth": form_data},
            )

        try:
            success, message = tool.authorize_youtube_with_code(code)
            result = {"authorized": success, "message": message}
            return _render_dashboard(
                action_result={
                    "title": "提交 YouTube 授权码",
                    "success": success,
                    "summary": message,
                    "data": result,
                    "data_pretty": _format_data(result),
                    "logs": logs,
                },
                form_defaults={"auth": {"code": ""}},
            )
        except Exception as exc:
            return _render_dashboard(
                action_result=_error_result("提交 YouTube 授权码", exc, logs),
                form_defaults={"auth": form_data},
            )

    @app.post("/schedule/run")
    def schedule_run():
        form_data = request.form.to_dict()
        logs: list[str] = []

        try:
            result = run_scheduled_upload(
                time_str=form_data.get("time") or None,
                limit=int(form_data["limit"]) if form_data.get("limit") else None,
                log_callback=logs.append,
            )
            if result.get("success") or result.get("failed_videos"):
                summary = (
                    f"成功 {result.get('success_count', 0)}，"
                    f"跳过 {result.get('skipped', 0)}，"
                    f"失败 {result.get('failed', 0)}。"
                )
            else:
                summary = result.get("message", "任务执行完成。")
            return _render_dashboard(
                action_result={
                    "title": "执行调度任务",
                    "success": bool(result.get("success")),
                    "summary": summary,
                    "data": result,
                    "data_pretty": _format_data(result),
                    "logs": logs,
                },
                form_defaults={"schedule": form_data},
            )
        except Exception as exc:
            return _render_dashboard(
                action_result=_error_result("执行调度任务", exc, logs),
                form_defaults={"schedule": form_data},
            )

    @app.post("/analyze/refresh")
    def analyze_refresh():
        from src.analyze import analyze_and_cache

        logs: list[str] = []
        force = bool(request.form.get("force"))
        try:
            cache = analyze_and_cache(force=force, log_callback=logs.append)
            if cache and cache.recommendation:
                summary = (
                    f"黄金时段 {cache.recommendation.optimal_time}，"
                    f"次选时段 {cache.recommendation.secondary_time}。"
                )
            else:
                summary = "分析完成，但没有生成推荐结果。"
            return _render_dashboard(
                action_result=_success_result("刷新受众分析", summary, _serialize_audience_cache(cache), logs),
            )
        except Exception as exc:
            return _render_dashboard(action_result=_error_result("刷新受众分析", exc, logs))

    return app


def _render_dashboard(
    action_result: dict[str, Any] | None = None,
    form_defaults: dict[str, dict[str, Any]] | None = None,
):
    tool = XHSToYouTube()
    overview = _build_overview(tool)
    defaults = _default_forms()
    if form_defaults:
        defaults.update(form_defaults)
    web_config = load_web_config()
    auth_enabled = bool(web_config.get("enabled")) and bool(web_config.get("username")) and bool(web_config.get("password"))
    csrf_token = _get_csrf_token() if bool(web_config.get("csrf_enabled")) else ""
    return render_template(
        "index.html",
        overview=overview,
        action_result=action_result,
        forms=defaults,
        web_auth_enabled=auth_enabled,
        web_csrf_enabled=bool(web_config.get("csrf_enabled")),
        csrf_token=csrf_token,
    )


def _build_overview(tool: XHSToYouTube) -> dict[str, Any]:
    statuses = []
    for key, status in tool.check_credentials().items():
        statuses.append(
            {
                "key": key,
                "name": status.name,
                "exists": status.exists,
                "valid": status.valid,
                "message": status.message,
                "path": status.path,
            }
        )

    return {
        "statuses": statuses,
        "quota": tool.check_upload_limit(),
        "schedule_status": get_today_schedule_status(),
        "recent_uploads": _load_recent_uploads(),
        "config_info": _load_config_info(),
        "auth_info": _load_auth_info(),
        "web_auth_info": _load_web_auth_info(),
        "audience": _load_audience_info(),
    }


def _default_forms() -> dict[str, dict[str, Any]]:
    return {
        "transfer": {"url": "", "title_en": "", "desc": "", "tags": "", "privacy": "public"},
        "fetch": {"url": "", "output": str(VIDEO_LIST_FILE), "page_size": "10"},
        "batch": {
            "input": str(VIDEO_LIST_FILE),
            "interval_min": "10",
            "interval_max": "30",
            "limit": "0",
            "privacy": "public",
        },
        "cookie": {"cookie_content": ""},
        "auth": {"code": ""},
        "schedule": {"time": "", "limit": ""},
    }


def _load_recent_uploads(limit: int = 8) -> list[dict[str, Any]]:
    if not UPLOADED_FILE.exists():
        return []
    try:
        payload = json.loads(UPLOADED_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    records = []
    for note_id, record in payload.get("records", {}).items():
        row = dict(record)
        row["note_id"] = note_id
        records.append(row)
    records.sort(key=lambda item: item.get("uploaded_at", ""), reverse=True)
    return records[:limit]


def _load_auth_info() -> dict[str, Any]:
    expiry = ""
    if TOKEN_FILE.exists():
        try:
            payload = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
            expiry = payload.get("expiry", "")
        except (OSError, json.JSONDecodeError):
            expiry = ""
    return {"token_exists": TOKEN_FILE.exists(), "token_expiry": expiry}


def _load_web_auth_info() -> dict[str, Any]:
    web_config = load_web_config()
    enabled = bool(web_config.get("enabled")) and bool(web_config.get("username")) and bool(web_config.get("password"))
    return {
        "enabled": enabled,
        "username": web_config.get("username", "") if enabled else "",
        "realm": web_config.get("realm", "xhs-to-youtube web console"),
        "csrf_enabled": bool(web_config.get("csrf_enabled")),
    }


def _get_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _reject_if_csrf_invalid():
    expected = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    if expected and supplied and supplied == expected:
        return None

    return Response("Invalid CSRF token", 400)


def _load_config_info() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {"config_exists": False, "video_list_exists": VIDEO_LIST_FILE.exists()}
    try:
        payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    proxies = payload.get("proxies", {})
    return {
        "config_exists": True,
        "video_list_exists": VIDEO_LIST_FILE.exists(),
        "proxy_enabled": bool(proxies.get("http") or proxies.get("https")),
        "config_path": str(CONFIG_FILE),
    }


def _load_audience_info() -> dict[str, Any]:
    from src.analyze import load_audience_cache

    cache = load_audience_cache()
    return _serialize_audience_cache(cache)


def _success_result(title: str, summary: str, data: Any, logs: list[str]) -> dict[str, Any]:
    return {
        "title": title,
        "success": True,
        "summary": summary,
        "data": data,
        "data_pretty": _format_data(data),
        "logs": logs,
    }


def _error_result(title: str, exc: Exception, logs: list[str]) -> dict[str, Any]:
    return {
        "title": title,
        "success": False,
        "summary": "".join(traceback.format_exception_only(type(exc), exc)).strip(),
        "data": None,
        "data_pretty": "",
        "logs": logs,
    }


def _format_data(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except TypeError:
        return str(data)


def _serialize_audience_cache(cache: Any) -> dict[str, Any] | None:
    if not cache:
        return None

    recommendation = getattr(cache, "recommendation", None)
    insight = getattr(cache, "insight", None)
    return {
        "analyzed_at": getattr(cache, "analyzed_at", ""),
        "total_views": getattr(cache, "total_views", 0),
        "recommendation": {
            "optimal_time": getattr(recommendation, "optimal_time", ""),
            "secondary_time": getattr(recommendation, "secondary_time", ""),
            "reason": getattr(recommendation, "reason", ""),
            "user_timezone": getattr(recommendation, "user_timezone", ""),
        }
        if recommendation
        else None,
        "insight": {
            "primary_age_group": getattr(insight, "primary_age_group", ""),
            "primary_age_percent": getattr(insight, "primary_age_percent", 0),
            "gender_ratio": getattr(insight, "gender_ratio", ""),
            "content_suggestion": getattr(insight, "content_suggestion", ""),
        }
        if insight
        else None,
    }


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
