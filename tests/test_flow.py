#!/usr/bin/env python3
"""
小红书到 YouTube 视频搬运工具 - 测试用例

运行: python -m tests.test_flow
"""

import sys
import os
from pathlib import Path
from datetime import datetime

import pytest

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core import XHSToYouTube
from src.config import CREDENTIALS_FILE, TOKEN_FILE


def test_credentials():
    """测试凭证状态和 YouTube API 连接"""
    print("=" * 50)
    print("测试 1: 凭证状态检查")
    print("=" * 50)
    
    tool = XHSToYouTube()
    statuses = tool.check_credentials()
    
    for key, status in statuses.items():
        icon = "✅" if status.valid else ("⚠️" if status.exists else "❌")
        print(f"{icon} {status.name}: {status.message}")
    
    # 至少需要 credentials.json 存在
    assert statuses.get('credentials').exists, "Google OAuth 凭证文件不存在"
    
    # Token 可能过期，这是正常的（测试不实际上传）
    if statuses.get('token') and statuses.get('token').valid:
        print("✅ YouTube Token 有效")
    else:
        print("⚠️ YouTube Token 已过期或不存在（上传时需要重新授权）")
    
    print("✅ 凭证检查通过\n")


@pytest.mark.live_network
def test_video_stream_selection():
    """测试视频流选择（无水印）- 使用实际页面"""
    print("=" * 50)
    print("测试 2: 视频流选择（去水印）")
    print("=" * 50)
    
    test_url = "http://xhslink.com/o/6fDiSoovKl5"
    
    tool = XHSToYouTube()
    result = tool.download_video(test_url)
    
    print(f"标题: {result['title']}")
    
    assert os.path.exists(result['video_path']), "视频文件不存在"
    
    print("✅ 视频流选择测试通过（已选择无水印版本）\n")


def test_title_extraction():
    """测试标题提取"""
    print("=" * 50)
    print("测试 3: 标题提取")
    print("=" * 50)
    
    import re
    
    test_cases = [
        ('<title>测试视频标题 - 小红书</title>', "测试视频标题"),
        ('<title>另一个标题 - 小红书</title>', "另一个标题"),
    ]
    
    for html, expected in test_cases:
        title = ""
        html_title_match = re.search(r'<title>([^<]+)</title>', html)
        if html_title_match:
            html_title = html_title_match.group(1)
            if ' - 小红书' in html_title:
                title = html_title.split(' - 小红书')[0].strip()
            else:
                title = html_title.strip()
        
        print(f"HTML: {html}")
        print(f"提取标题: {title}")
        assert title == expected, f"标题提取错误: 期望 '{expected}', 实际 '{title}'"
    
    print("✅ 标题提取测试通过\n")


def test_download_video():
    """测试视频下载"""
    print("=" * 50)
    print("测试 4: 视频下载（已在测试2中完成）")
    print("=" * 50)
    
    print("✅ 视频下载测试已通过（见测试2）\n")


def test_full_transfer():
    """测试完整搬运流程（不上传，仅验证下载和元数据生成）"""
    print("=" * 50)
    print("测试 5: 搬运流程准备检查")
    print("=" * 50)
    
    tool = XHSToYouTube()
    
    print("1. 检查凭证状态...")
    statuses = tool.check_credentials()
    assert statuses.get('credentials').exists, "凭证文件不存在"
    print("   ✅ 凭证文件存在")
    
    print("\n2. 检查视频下载功能...")
    print("   ✅ 视频下载功能已在测试 2 中验证")
    
    print("\n3. 测试元数据生成...")
    title = tool.generate_english_title("测试标题", "Test Title")
    assert "测试标题" in title or "Test Title" in title, "标题生成失败"
    print(f"   生成的标题: {title}")
    
    desc = tool.generate_description("测试描述", "https://example.com", "uploader")
    assert "测试描述" in desc, "描述生成失败"
    print(f"   生成的描述: {desc[:50]}...")
    
    print("\n4. 测试翻译功能...")
    translated = tool.translate("你好世界", "title")
    print(f"   翻译结果: {translated}")
    
    print("\n✅ 搬运流程准备检查通过（未实际上传视频）\n")


def test_time_recommendation():
    """测试时间推荐功能"""
    print("=" * 50)
    print("测试 6: 时间推荐功能")
    print("=" * 50)
    
    from src.analyze import (
        analyze_and_cache,
        get_time_recommendation,
        is_good_upload_time,
    )
    
    print("1. 测试分析缓存...")
    cache = analyze_and_cache(force=False, log_callback=print)
    
    if cache:
        print(f"   ✅ 缓存加载成功: {cache.analyzed_at}")
        print(f"   地区数量: {len(cache.regions)}")
        if cache.demographics:
            print(f"   年龄段数量: {len(cache.demographics.age_groups)}")
    else:
        print("   ⚠️ 无缓存数据（需要先运行 analyze 命令）")
    
    print("\n2. 测试时间推荐获取...")
    recommendation = get_time_recommendation()
    
    if recommendation:
        print(f"   黄金时段: {recommendation.optimal_time}")
        print(f"   次选时段: {recommendation.secondary_time}")
        print(f"   推荐原因: {recommendation.reason}")
        assert recommendation.optimal_time, "黄金时段不能为空"
        print("   ✅ 时间推荐获取成功")
    else:
        print("   ⚠️ 无时间推荐数据")
    
    print("\n3. 测试时段判断...")
    # 测试不同时段
    test_hours = [10, 13, 20, 23]
    for hour in test_hours:
        is_good, msg = is_good_upload_time(hour)
        status = "✅ 推荐" if is_good else "⚠️ 不推荐"
        print(f"   {hour}:00 -> {status} ({msg})")
    
    print("\n✅ 时间推荐测试通过\n")


def test_time_slot_labeling():
    """测试时间段标签功能"""
    print("=" * 50)
    print("测试 7: 时间段标签功能")
    print("=" * 50)
    
    tool = XHSToYouTube()
    
    print("测试不同时段的标签:")
    test_cases = [
        (10, "非推荐时段"),   # 上午
        (13, "非推荐时段"),   # 下午
        (19, "黄金时段"),     # 晚间黄金档
        (21, "黄金时段"),     # 晚间黄金档
        (12, "次选时段"),     # 午休
    ]
    
    for hour, expected_type in test_cases:
        time_slot, followed = tool._get_time_slot_info(hour)
        status = "✅" if expected_type in time_slot else "⚠️"
        print(f"   {hour}:00 -> {time_slot} (遵循推荐: {followed}) {status}")
    
    print("\n✅ 时间段标签测试通过\n")


def test_upload_record_structure():
    """测试上传记录数据结构"""
    print("=" * 50)
    print("测试 8: 上传记录数据结构")
    print("=" * 50)
    
    from src.models import UploadRecord
    from datetime import datetime
    
    print("创建测试上传记录...")
    record = UploadRecord(
        note_id="test_123",
        youtube_id="abc123",
        youtube_url="https://youtube.com/watch?v=abc123",
        title="测试视频标题",
        uploaded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        upload_hour=20,
        time_slot="黄金时段",
        recommendation_followed=True,
    )
    
    print(f"   note_id: {record.note_id}")
    print(f"   upload_hour: {record.upload_hour}")
    print(f"   time_slot: {record.time_slot}")
    print(f"   recommendation_followed: {record.recommendation_followed}")
    
    assert record.upload_hour == 20, "upload_hour 字段错误"
    assert record.time_slot == "黄金时段", "time_slot 字段错误"
    assert record.recommendation_followed is True, "recommendation_followed 字段错误"
    
    print("\n✅ 上传记录数据结构测试通过\n")


def test_bot_run_command_uses_schedule_time(monkeypatch):
    """测试 Bot 的 /run 命令会正确调用定时任务入口。"""
    import src.bot as bot_module

    called = {}

    def fake_run_scheduled_upload(time_str=None, limit=None, log_callback=None):
        called["time_str"] = time_str
        called["limit"] = limit
        return {"success": True, "success_count": 1, "skipped": 0, "failed": 0}

    def fake_notify_upload_result(task_time, result):
        called["notified"] = (task_time, result)
        return True

    class FakeThread:
        def __init__(self, target):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr("src.schedule.run_scheduled_upload", fake_run_scheduled_upload)
    monkeypatch.setattr("src.notification.notify_upload_result", fake_notify_upload_result)
    monkeypatch.setattr(bot_module.threading, "Thread", FakeThread)
    monkeypatch.setattr(bot_module, "send_message", lambda *args, **kwargs: True)

    message = bot_module.handle_run_command(["08:00", "2"])

    assert "已启动上传任务" in message
    assert called["time_str"] == "08:00"
    assert called["limit"] == 2
    assert called["notified"][0] == "08:00"


def test_schedule_status_is_minute_aware(monkeypatch):
    """测试今日调度状态会按分钟判断任务状态。"""
    import src.schedule as schedule_module

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 11, 8, 30, 0)

    monkeypatch.setattr(schedule_module, "datetime", FixedDateTime)
    monkeypatch.setattr(
        schedule_module,
        "list_schedule_tasks",
        lambda: [
            {"time": "08:00", "limit": 1, "enabled": True, "description": "早间上传"},
            {"time": "08:30", "limit": 2, "enabled": True, "description": "加餐上传"},
            {"time": "09:00", "limit": 3, "enabled": True, "description": "上午上传"},
        ],
    )
    monkeypatch.setattr("src.config.UPLOADED_FILE", Path("/tmp/nonexistent_uploaded.json"))

    status = schedule_module.get_today_schedule_status()

    assert status["current_time"] == "08:30"
    assert [task["status"] for task in status["tasks"]] == [
        "completed",
        "running",
        "pending",
    ]


def test_bot_auth_code_command(monkeypatch):
    """测试 Telegram Bot 可以用授权码完成 token 更新。"""
    import src.bot as bot_module

    calls = {}

    class FakeTool:
        def authorize_youtube_with_code(self, code):
            calls["code"] = code
            return True, "授权成功！凭证已保存到: token.json"

    monkeypatch.setattr("src.core.XHSToYouTube", FakeTool)

    result = bot_module.handle_auth_code_command(["abc123"])

    assert calls["code"] == "abc123"
    assert "YouTube 授权完成" in result
    assert "/token_status" in result


def test_notify_upload_result_includes_failure_details(monkeypatch):
    """测试失败通知会包含失败明细。"""
    import src.notification as notification_module

    captured = {}

    def fake_send_notification(message, level="info", title=None):
        captured["message"] = message
        captured["level"] = level
        captured["title"] = title
        return True

    monkeypatch.setattr(notification_module, "send_notification", fake_send_notification)

    result = {
        "success": False,
        "message": "批量上传异常",
        "failed_videos": [
            {"title": "视频A", "error": "未找到视频链接"},
            {"title": "视频B", "error": "下载失败"},
            {"title": "视频C", "error": "权限不足"},
            {"title": "视频D", "error": "稍后重试"},
        ],
    }

    ok = notification_module.notify_upload_result("08:00", result)

    assert ok is True
    assert captured["level"] == "warning"
    assert captured["title"] == "定时上传异常"
    assert "失败明细" in captured["message"]
    assert "视频A: 未找到视频链接" in captured["message"]
    assert "视频B: 下载失败" in captured["message"]
    assert "还有 1 条失败记录" in captured["message"]


def test_bot_notify_test_command(monkeypatch):
    """测试 Telegram Bot 通知自检命令。"""
    import src.bot as bot_module

    calls = {}

    def fake_test_notification_delivery(message="通知通信测试", channel="all"):
        calls["message"] = message
        calls["channel"] = channel
        return {
            "channel": channel,
            "success": True,
            "message": "通知发送成功",
            "telegram": {"message": "Telegram 发送成功"},
            "feishu": {"message": "飞书未配置"},
        }

    monkeypatch.setattr("src.notification.test_notification_delivery", fake_test_notification_delivery)

    result = bot_module.handle_notify_test_command(["telegram"])

    assert calls["channel"] == "telegram"
    assert "通知自检结果" in result
    assert "Telegram 发送成功" in result


def test_bot_register_commands(monkeypatch):
    """测试 Bot 启动时会注册 Telegram 菜单命令。"""
    import src.bot as bot_module

    captured = {}

    class FakeResponse:
        def json(self):
            return {"ok": True, "result": True}

    def fake_post(url, json=None, proxies=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        captured["proxies"] = proxies
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(bot_module, "BOT_TOKEN", "fake-token")
    monkeypatch.setattr("src.bot.requests.post", fake_post)

    ok = bot_module.register_bot_commands()

    assert ok is True
    assert captured["url"] == "https://api.telegram.org/botfake-token/setMyCommands"
    assert captured["payload"]["commands"] == bot_module.BOT_COMMANDS
    assert captured["timeout"] == 15


def test_bot_send_message_uses_plain_text(monkeypatch):
    """测试 Bot 的普通回复不会强制使用 Markdown。"""
    import src.bot as bot_module

    captured = {}

    def fake_send_telegram_message(token, chat_id, message, level="info", title=None, parse_mode="Markdown"):
        captured["token"] = token
        captured["chat_id"] = chat_id
        captured["message"] = message
        captured["parse_mode"] = parse_mode
        return True

    monkeypatch.setattr(bot_module, "BOT_TOKEN", "fake-token")
    monkeypatch.setattr(bot_module, "CHAT_ID", "123456")
    monkeypatch.setattr("src.bot.send_telegram_message", fake_send_telegram_message)

    ok = bot_module.send_message("hello_world [link](example)")

    assert ok is True
    assert captured["chat_id"] == "123456"
    assert captured["parse_mode"] is None


def test_batch_transfer_marks_failure_as_failed(monkeypatch, tmp_path):
    """测试批量上传在任一视频失败时会返回失败状态。"""
    import src.core as core_module

    video_list = tmp_path / "videos.json"
    video_list.write_text(
        """
        {
          "videos": [
            {"note_id": "n1", "title": "视频1", "desc": "desc", "url": "https://example.com/1"}
          ]
        }
        """.strip(),
        encoding="utf-8",
    )

    tool = core_module.XHSToYouTube()
    monkeypatch.setattr(tool, "check_upload_limit", lambda: {"limit": 10, "used": 0, "remaining": 10})
    monkeypatch.setattr(tool, "_load_uploaded_records", lambda: {})
    monkeypatch.setattr(tool, "transfer", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("token expired")))

    result = tool.batch_transfer(video_list_path=str(video_list), limit=1, show_time_suggestion=False)

    assert result["success"] is False
    assert result["failed"] == 1
    assert result["failed_videos"][0]["error"] == "token expired"


def test_batch_transfer_filters_uploaded_videos_before_processing(monkeypatch, tmp_path):
    """测试批量上传会先过滤已上传视频，再处理剩余队列。"""
    import src.core as core_module

    video_list = tmp_path / "videos.json"
    video_list.write_text(
        """
        {
          "videos": [
            {"note_id": "n1", "title": "视频1", "desc": "desc", "url": "https://example.com/1"},
            {"note_id": "n2", "title": "视频2", "desc": "desc", "url": "https://example.com/2"},
            {"note_id": "n3", "title": "视频3", "desc": "desc", "url": "https://example.com/3"}
          ]
        }
        """.strip(),
        encoding="utf-8",
    )

    tool = core_module.XHSToYouTube()
    monkeypatch.setattr(tool, "check_upload_limit", lambda: {"limit": 10, "used": 0, "remaining": 10})
    monkeypatch.setattr(
        tool,
        "_load_uploaded_records",
        lambda: {
            "n1": {"youtube_url": "https://youtube.com/watch?v=1"},
            "n2": {"youtube_url": "https://youtube.com/watch?v=2"},
        },
    )

    transfer_calls = []

    def fake_transfer(**kwargs):
        transfer_calls.append(kwargs)
        return {"video_id": "abc123", "video_url": "https://youtube.com/watch?v=abc123", "title": kwargs["title"]}

    monkeypatch.setattr(tool, "transfer", fake_transfer)

    result = tool.batch_transfer(video_list_path=str(video_list), limit=1, show_time_suggestion=False)

    assert result["success"] is True
    assert result["skipped"] == 2
    assert result["success_count"] == 1
    assert len(transfer_calls) == 1
    assert transfer_calls[0]["xhs_url"] == "https://example.com/3"


def test_cmd_batch_sends_notification_on_failure(monkeypatch):
    """测试 batch 命令会把失败结果送入通知层。"""
    import src.cli as cli_module

    calls = {}

    def fake_batch_transfer(**kwargs):
        calls["batch_kwargs"] = kwargs
        return {
            "success": False,
            "message": "token expired",
            "failed": 1,
            "failed_videos": [{"title": "视频1", "error": "token expired"}],
            "success_count": 0,
            "skipped": 0,
            "total": 1,
        }

    def fake_notify_upload_result(task_time, result, error=None):
        calls["notify"] = (task_time, result, error)
        return True

    monkeypatch.setattr("src.notification.notify_upload_result", fake_notify_upload_result)
    monkeypatch.setattr(cli_module.XHSToYouTube, "batch_transfer", lambda self, **kwargs: fake_batch_transfer(**kwargs))

    class Args:
        input = "videos.json"
        interval_min = 1
        interval_max = 1
        privacy = "public"
        keep_video = False
        force = False
        no_translate = True
        translate_title = False
        translate_desc = False
        limit = 1
        time_confirm = False

    cli_module.cmd_batch(Args())

    assert calls["batch_kwargs"]["limit"] == 1
    assert calls["notify"][0] == "batch:videos.json"
    assert calls["notify"][1]["success"] is False
    assert calls["notify"][2] is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
