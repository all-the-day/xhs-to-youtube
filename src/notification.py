"""
通知模块

提供飞书、Telegram 等通知渠道的发送功能。
"""

import json
from typing import Any
from datetime import datetime

import requests

from src.config import load_schedule_config, SCRIPT_DIR

# 获取代理 URL
def get_proxy_url() -> str:
    """从配置获取代理 URL"""
    config = load_schedule_config()
    proxies = config.get("proxies", {})
    proxy = proxies.get("http") or proxies.get("https") or proxies.get("https_proxy", "")
    return proxy if proxy else ""

PROXY_URL = get_proxy_url()


def send_notification(
    message: str,
    level: str = "info",
    title: str | None = None,
) -> bool:
    """发送通知（统一入口）
    
    Args:
        message: 通知内容
        level: 通知级别 (info, success, warning, error)
        title: 通知标题（可选）
    
    Returns:
        是否发送成功
    """
    config = load_schedule_config()
    notification_config = config.get("notification", {})
    
    if not notification_config.get("enabled", False):
        return False
    
    # 根据级别决定是否发送
    if level == "success" and not notification_config.get("notify_on_success", False):
        return False
    
    if level == "error" and not notification_config.get("notify_on_failure", True):
        return False
    
    results = []
    
    # 发送 Telegram 通知
    tg_token = notification_config.get("telegram_token", "")
    tg_chat_id = notification_config.get("telegram_chat_id", "")
    if tg_token and tg_chat_id:
        results.append(send_telegram_message(tg_token, tg_chat_id, message, level, title))
    
    # 发送飞书通知
    webhook = notification_config.get("feishu_webhook", "")
    if webhook:
        results.append(send_feishu_message(webhook, message, level, title))
    
    return any(results) if results else False


def send_telegram_message(
    token: str,
    chat_id: str,
    message: str,
    level: str = "info",
    title: str | None = None,
    parse_mode: str | None = "Markdown",
) -> bool:
    """发送 Telegram 消息
    
    Args:
        token: Telegram Bot Token
        chat_id: Chat ID
        message: 消息内容
        level: 消息级别 (info, success, warning, error)
        title: 消息标题
    
    Returns:
        是否发送成功
    """
    # 根据级别选择图标
    icon_map = {
        "info": "📢",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
    }
    icon = icon_map.get(level, "📢")
    
    # 构建消息标题
    if not title:
        title_map = {
            "info": "通知",
            "success": "成功",
            "warning": "警告",
            "error": "错误",
        }
        title = title_map.get(level, "通知")
    
    # 构建消息文本
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    text = f"*{icon} {title}*\n\n{message}\n\n_时间: {timestamp}_"
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    
    proxy_url = get_proxy_url()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    
    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            proxies=proxies,
            timeout=10,
        )
        result = response.json()
        return result.get("ok", False)
    except Exception as e:
        print(f"Telegram 通知发送失败: {e}")
        return False


def send_feishu_message(
    webhook: str,
    message: str,
    level: str = "info",
    title: str | None = None,
) -> bool:
    """发送飞书消息
    
    Args:
        webhook: 飞书 Webhook URL
        message: 消息内容
        level: 消息级别 (info, success, warning, error)
        title: 消息标题
    
    Returns:
        是否发送成功
    """
    # 根据级别选择颜色
    color_map = {
        "info": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
    }
    color = color_map.get(level, "blue")
    
    # 构建消息标题
    if not title:
        title_map = {
            "info": "📢 通知",
            "success": "✅ 成功",
            "warning": "⚠️ 警告",
            "error": "❌ 错误",
        }
        title = title_map.get(level, "📢 通知")
    
    # 构建飞书卡片消息
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True,
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
                "template": color,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": message,
                    },
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    },
                },
            ],
        },
    }
    
    try:
        response = requests.post(
            webhook,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False


def test_notification_delivery(
    message: str = "通知通信测试",
    channel: str = "all",
) -> dict[str, Any]:
    """测试通知通道连通性。

    Args:
        message: 发送的测试消息内容
        channel: 目标通道，支持 all/telegram/feishu

    Returns:
        包含配置检查和发送结果的字典
    """
    config = load_schedule_config()
    notification_config = config.get("notification", {})
    enabled = notification_config.get("enabled", False)

    result: dict[str, Any] = {
        "enabled": enabled,
        "channel": channel,
        "success": False,
        "telegram": {
            "configured": False,
            "success": False,
            "message": "",
        },
        "feishu": {
            "configured": False,
            "success": False,
            "message": "",
        },
    }

    if not enabled:
        result["message"] = "通知功能未启用"
        return result

    target_all = channel == "all"
    target_telegram = target_all or channel == "telegram"
    target_feishu = target_all or channel == "feishu"

    tg_token = notification_config.get("telegram_token", "")
    tg_chat_id = notification_config.get("telegram_chat_id", "")
    if target_telegram:
        result["telegram"]["configured"] = bool(tg_token and tg_chat_id)
        if result["telegram"]["configured"]:
            result["telegram"]["success"] = send_telegram_message(
                tg_token,
                tg_chat_id,
                message,
                "info",
                "通知通信测试",
            )
            result["telegram"]["message"] = (
                "Telegram 发送成功" if result["telegram"]["success"] else "Telegram 发送失败"
            )
        else:
            result["telegram"]["message"] = "Telegram 未配置完整"

    webhook = notification_config.get("feishu_webhook", "")
    if target_feishu:
        result["feishu"]["configured"] = bool(webhook)
        if result["feishu"]["configured"]:
            result["feishu"]["success"] = send_feishu_message(
                webhook,
                message,
                "info",
                "通知通信测试",
            )
            result["feishu"]["message"] = (
                "飞书发送成功" if result["feishu"]["success"] else "飞书发送失败"
            )
        else:
            result["feishu"]["message"] = "飞书未配置"

    result["success"] = any(
        [
            result["telegram"]["success"],
            result["feishu"]["success"],
        ]
    )

    if not result["success"]:
        if target_all and not result["telegram"]["configured"] and not result["feishu"]["configured"]:
            result["message"] = "没有可用的通知通道"
        else:
            result["message"] = "通知发送失败"
    else:
        result["message"] = "通知发送成功"

    return result


def notify_upload_result(
    task_time: str,
    result: dict[str, Any],
    error: str | None = None,
) -> bool:
    """发送上传结果通知
    
    Args:
        task_time: 任务时间
        result: 上传结果
        error: 错误信息
    
    Returns:
        是否发送成功
    """
    if error:
        level = "error"
        title = "定时上传失败"
        message = f"任务时间: {task_time}\n错误信息: {error}"
    elif result.get("success"):
        level = "success"
        title = "定时上传完成"
        success_count = result.get("success_count", 0)
        skipped = result.get("skipped", 0)
        failed = result.get("failed", 0)
        message = (
            f"任务时间: {task_time}\n"
            f"成功: {success_count} 个\n"
            f"跳过: {skipped} 个\n"
            f"失败: {failed} 个"
        )
    else:
        level = "warning"
        title = "定时上传异常"
        message = f"任务时间: {task_time}\n信息: {result.get('message', '未知错误')}"

        failed_videos = result.get("failed_videos", [])
        if failed_videos:
            details = []
            for video in failed_videos[:3]:
                video_title = video.get("title", "未知标题")
                video_error = video.get("error", "未知错误")
                details.append(f"- {video_title}: {video_error}")

            if details:
                message += "\n\n失败明细:\n" + "\n".join(details)
                if len(failed_videos) > 3:
                    message += f"\n- ... 还有 {len(failed_videos) - 3} 条失败记录"
    
    return send_notification(message, level, title)


def notify_daily_summary(today_uploads: int, tasks_status: list[dict]) -> bool:
    """发送每日汇总通知
    
    Args:
        today_uploads: 今日上传总数
        tasks_status: 任务状态列表
    
    Returns:
        是否发送成功
    """
    title = "每日上传汇总"
    
    # 构建任务状态文本
    status_lines = []
    for task in tasks_status:
        status_icon = {
            "completed": "✅",
            "running": "🔄",
            "pending": "⏳",
        }.get(task["status"], "❓")
        status_lines.append(
            f"{status_icon} {task['time']} - {task['description']} (计划: {task['limit']})"
        )
    
    message = (
        f"今日上传总数: {today_uploads}\n\n"
        f"任务状态:\n" + "\n".join(status_lines)
    )
    
    return send_notification(message, "info", title)
