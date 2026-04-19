from __future__ import annotations

import base64
import re
from dataclasses import dataclass

import pytest

from src.web import create_app


@dataclass
class FakeStatus:
    name: str
    exists: bool
    valid: bool
    message: str
    path: str


class FakeTool:
    last_instance: "FakeTool | None" = None

    def __init__(self, log_callback=None, progress_callback=None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.transfer_calls = []
        self.fetch_calls = []
        self.batch_calls = []
        self.cookie_updates = []
        self.auth_codes = []
        FakeTool.last_instance = self

    def check_credentials(self):
        return {
            "cookie": FakeStatus("小红书 Cookie", True, True, "已配置", "/tmp/cookies.txt"),
            "token": FakeStatus("YouTube Token", True, False, "未授权", "/tmp/token.json"),
        }

    def check_upload_limit(self):
        return {"limit": 10, "used": 2, "remaining": 8}

    def transfer(self, **kwargs):
        self.transfer_calls.append(kwargs)
        if self.log_callback:
            self.log_callback("transfer called")
        return {"video_id": "vid-1", "video_url": "https://youtube.com/watch?v=vid-1"}

    def fetch_user_videos(self, **kwargs):
        self.fetch_calls.append(kwargs)
        if self.log_callback:
            self.log_callback("fetch called")
        return {"total_count": 3, "videos": [{"title": "A"}]}

    def batch_transfer(self, **kwargs):
        self.batch_calls.append(kwargs)
        if self.log_callback:
            self.log_callback("batch called")
        return {
            "success": True,
            "success_count": 2,
            "skipped": 1,
            "failed": 0,
            "failed_videos": [],
        }

    def update_cookie(self, content: str):
        self.cookie_updates.append(content)
        return True

    def get_authorization_url(self):
        return True, "https://example.com/auth"

    def authorize_youtube_with_code(self, code: str):
        self.auth_codes.append(code)
        return True, "授权完成"


def build_client(monkeypatch, web_config=None):
    monkeypatch.setattr("src.web.XHSToYouTube", FakeTool)
    monkeypatch.setattr(
        "src.web.load_web_config",
        lambda: web_config
        or {
            "enabled": False,
            "username": "",
            "password": "",
            "csrf_enabled": False,
            "secret_key": "",
            "realm": "xhs-to-youtube web console",
        },
    )
    monkeypatch.setattr(
        "src.web.get_today_schedule_status",
        lambda: {
            "date": "2026-04-18",
            "current_time": "09:00",
            "today_uploads": 2,
            "tasks": [{"time": "08:00", "limit": 3, "description": "早间上传", "status": "completed"}],
        },
    )
    monkeypatch.setattr("src.web._load_recent_uploads", lambda limit=8: [])
    monkeypatch.setattr("src.web._load_auth_info", lambda: {"token_exists": True, "token_expiry": ""})
    monkeypatch.setattr(
        "src.web._load_config_info",
        lambda: {"config_exists": True, "video_list_exists": True, "proxy_enabled": False, "config_path": "/tmp/config.json"},
    )
    monkeypatch.setattr("src.web._load_audience_info", lambda: None)
    monkeypatch.setattr(
        "src.web.run_scheduled_upload",
        lambda time_str=None, task_time=None, limit=None, log_callback=None: {
            "success": True,
            "success_count": 1,
            "skipped": 0,
            "failed": 0,
            "failed_videos": [],
        },
    )
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_index_renders_dashboard(monkeypatch):
    client = build_client(monkeypatch)

    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "浏览器里直接搬运小红书视频到 YouTube" in body
    assert "凭证状态" in body
    assert "调度状态" in body


def test_transfer_route_disables_interactive_prompt(monkeypatch):
    client = build_client(monkeypatch)

    response = client.post(
        "/transfer",
        data={
            "url": "https://www.xiaohongshu.com/explore/abc",
            "privacy": "unlisted",
            "translate": "on",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "视频已提交到 YouTube" in body

    # Find the instance that actually received the calls
    # The issue is that multiple instances are created, we need the first one
    instances = []
    original_init = FakeTool.__init__

    def tracking_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        instances.append(self)

    # Re-run the request with instance tracking
    with monkeypatch.context() as m:
        m.setattr(FakeTool, '__init__', tracking_init)
        # Reset instances list
        instances.clear()
        # Reset last_instance to ensure fresh tracking
        FakeTool.last_instance = None

        response = client.post(
            "/transfer",
            data={
                "url": "https://www.xiaohongshu.com/explore/abc",
                "privacy": "unlisted",
                "translate": "on",
            },
        )

        assert response.status_code == 200
        assert "视频已提交到 YouTube" in body

        # Use the first instance that received calls
        if instances:
            tool_instance = instances[0]
            assert len(tool_instance.transfer_calls) > 0
            last_call = tool_instance.transfer_calls[-1]
            assert last_call["show_time_suggestion"] is False
            assert last_call["privacy"] == "unlisted"
            assert last_call["translate"] is True
        else:
            # Fallback to last_instance if no instances tracked
            last_tool = FakeTool.last_instance
            assert last_tool is not None
            assert len(last_tool.transfer_calls) > 0
            last_call = last_tool.transfer_calls[-1]
            assert last_call["show_time_suggestion"] is False
            assert last_call["privacy"] == "unlisted"
            assert last_call["translate"] is True


def test_auth_url_route_shows_generated_link(monkeypatch):
    client = build_client(monkeypatch)

    response = client.post("/auth/url")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "已生成 YouTube 授权链接" in body
    assert "https://example.com/auth" in body


def test_cookie_route_requires_content(monkeypatch):
    client = build_client(monkeypatch)

    response = client.post("/cookie", data={"cookie_content": ""})

    assert response.status_code == 200
    assert "Cookie 内容不能为空" in response.get_data(as_text=True)


def test_web_authentication_required_when_enabled(monkeypatch):
    client = build_client(
        monkeypatch,
        web_config={
            "enabled": True,
            "username": "admin",
            "password": "secret",
            "csrf_enabled": False,
            "secret_key": "test-secret",
            "realm": "xhs-to-youtube web console",
        },
    )

    response = client.get("/")

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert "Basic realm=\"xhs-to-youtube web console\"" in response.headers["WWW-Authenticate"]


def test_web_requires_credentials_when_enabled(monkeypatch):
    with pytest.raises(ValueError, match="web.enabled=true requires non-empty web.username and web.password"):
        build_client(
            monkeypatch,
            web_config={
                "enabled": True,
                "username": "admin",
                "password": "",
                "csrf_enabled": False,
                "secret_key": "test-secret",
                "realm": "xhs-to-youtube web console",
            },
        )


def test_web_authentication_allows_valid_credentials(monkeypatch):
    client = build_client(
        monkeypatch,
        web_config={
            "enabled": True,
            "username": "admin",
            "password": "secret",
            "csrf_enabled": False,
            "secret_key": "test-secret",
            "realm": "xhs-to-youtube web console",
        },
    )

    token = base64.b64encode(b"admin:secret").decode("ascii")
    response = client.get("/", headers={"Authorization": f"Basic {token}"})

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "访问控制" in body


def test_web_csrf_token_is_required_when_enabled(monkeypatch):
    client = build_client(
        monkeypatch,
        web_config={
            "enabled": False,
            "username": "",
            "password": "",
            "csrf_enabled": True,
            "secret_key": "test-secret",
            "realm": "xhs-to-youtube web console",
        },
    )

    index_response = client.get("/")
    body = index_response.get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert match is not None

    rejected = client.post("/cookie", data={"cookie_content": "abc"})
    assert rejected.status_code == 400
    assert "Invalid CSRF token" in rejected.get_data(as_text=True)

    response = client.post("/cookie", data={"cookie_content": "abc", "csrf_token": match.group(1)})

    assert response.status_code == 200
    assert "Cookie 已更新" in response.get_data(as_text=True)
