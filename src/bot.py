#!/usr/bin/env python3
"""
Telegram Bot 服务

提供远程控制和状态查询功能。
"""

import json
import time
import threading
from datetime import datetime
from typing import Any

import requests

from src.config import load_schedule_config, SCRIPT_DIR, CONFIG_FILE
from src.notification import send_telegram_message, get_proxy_url

# Bot 配置
BOT_TOKEN = None
CHAT_ID = None
POLLING_INTERVAL = 5  # 轮询间隔（秒）
LAST_UPDATE_ID = 0


def load_bot_config():
    """加载 Bot 配置"""
    global BOT_TOKEN, CHAT_ID
    config = load_schedule_config()
    notification = config.get("notification", {})
    BOT_TOKEN = notification.get("telegram_token", "")
    CHAT_ID = notification.get("telegram_chat_id", "")


def get_updates(offset: int = 0) -> list[dict]:
    """获取新消息"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 10}
    proxy_url = get_proxy_url()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    
    try:
        response = requests.get(url, params=params, proxies=proxies, timeout=15)
        result = response.json()
        if result.get("ok"):
            return result.get("result", [])
    except Exception as e:
        print(f"获取消息失败: {e}")
    return []


def send_message(text: str, chat_id: str = None) -> bool:
    """发送消息"""
    if not chat_id:
        chat_id = CHAT_ID
    return send_telegram_message(BOT_TOKEN, chat_id, text, "info", None)


def handle_command(command: str, args: list[str], chat_id: str) -> str:
    """处理命令"""
    command = command.lower()
    
    if command == "start" or command == "help":
        return """🤖 *XHS to YouTube Bot*

可用命令:
/status - 查看今日上传状态
/tasks - 查看定时任务列表
/run [时间] [数量] - 手动触发上传
/enable <时间> - 启用任务
/disable <时间> - 禁用任务
/token_status - 检查凭证状态
/update_token - 更新YouTube授权
/help - 显示帮助信息"""
    
    elif command == "status":
        return get_status_message()
    
    elif command == "tasks":
        return get_tasks_message()
    
    elif command == "run":
        return handle_run_command(args)
    
    elif command == "enable":
        return handle_enable_command(args, enable=True)
    
    elif command == "disable":
        return handle_enable_command(args, enable=False)
    
    elif command == "token_status":
        return get_token_status_message()
    
    elif command == "update_token":
        return handle_update_token_command()
    
    else:
        return f"未知命令: /{command}\n使用 /help 查看可用命令"


def get_status_message() -> str:
    """获取状态消息"""
    from src.schedule import get_today_schedule_status
    
    status = get_today_schedule_status()
    
    lines = [
        f"📊 *今日上传状态*",
        f"",
        f"📅 日期: {status['date']}",
        f"🕐 当前时间: {status['current_time']}",
        f"📤 今日已上传: {status['today_uploads']} 个",
        f"",
        f"*任务状态:*",
    ]
    
    for task in status["tasks"]:
        icon = {"completed": "✅", "running": "🔄", "pending": "⏳"}.get(task["status"], "❓")
        lines.append(f"{icon} {task['time']} - {task['description']} (计划: {task['limit']})")
    
    return "\n".join(lines)


def get_tasks_message() -> str:
    """获取任务列表消息"""
    from src.schedule import list_schedule_tasks
    
    tasks = list_schedule_tasks()
    
    lines = ["📋 *定时任务列表*", ""]
    
    for i, task in enumerate(tasks, 1):
        status = "✅ 启用" if task.get("enabled", True) else "❌ 禁用"
        lines.append(f"{i}. {task['time']} - {task['description']}")
        lines.append(f"   状态: {status} | 数量: {task.get('limit', 3)}")
    
    return "\n".join(lines)


def handle_run_command(args: list[str]) -> str:
    """处理 run 命令"""
    from src.schedule import run_scheduled_upload
    from src.config import load_schedule_config
    
    config = load_schedule_config()
    default_limit = config.get("default_limit", 3)
    
    # 解析参数
    task_time = args[0] if args else datetime.now().strftime("%H:%M")
    limit = int(args[1]) if len(args) > 1 else default_limit
    
    # 验证时间格式
    try:
        datetime.strptime(task_time, "%H:%M")
    except ValueError:
        return f"❌ 时间格式错误: {task_time}\n正确格式: HH:MM (如 08:00)"
    
    # 在后台执行上传
    def run_in_background():
        try:
            result = run_scheduled_upload(task_time=task_time, limit=limit)
            # 发送结果通知
            from src.notification import notify_upload_result
            notify_upload_result(task_time, result)
        except Exception as e:
            send_message(f"❌ 上传任务执行失败: {e}")
    
    thread = threading.Thread(target=run_in_background)
    thread.start()
    
    return f"🚀 已启动上传任务\n时间: {task_time}\n数量: {limit} 个视频"


def handle_enable_command(args: list[str], enable: bool) -> str:
    """处理 enable/disable 命令"""
    if not args:
        return f"❌ 请指定任务时间\n用法: /{'enable' if enable else 'disable'} <时间>"
    
    task_time = args[0]
    
    # 验证时间格式
    try:
        datetime.strptime(task_time, "%H:%M")
    except ValueError:
        return f"❌ 时间格式错误: {task_time}\n正确格式: HH:MM (如 08:00)"
    
    # 更新配置
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        tasks = config.get("schedule", {}).get("tasks", [])
        found = False
        
        for task in tasks:
            if task["time"] == task_time:
                task["enabled"] = enable
                found = True
                break
        
        if not found:
            return f"❌ 未找到任务: {task_time}"
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        action = "启用" if enable else "禁用"
        return f"✅ 已{action}任务: {task_time}"
    
    except Exception as e:
        return f"❌ 操作失败: {e}"


def process_update(update: dict):
    """处理单条更新"""
    global LAST_UPDATE_ID
    
    message = update.get("message", {})
    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))
    text = message.get("text", "")
    update_id = update.get("update_id", 0)
    
    # 更新最后处理的 ID
    LAST_UPDATE_ID = update_id + 1
    
    # 只处理授权的 Chat ID
    if chat_id != CHAT_ID:
        print(f"未授权的消息来源: {chat_id}")
        return
    
    # 只处理命令
    if not text.startswith("/"):
        return
    
    # 解析命令
    parts = text[1:].split()
    command = parts[0].split("@")[0]  # 移除 @bot_name
    args = parts[1:]
    
    print(f"收到命令: /{command} {args}")
    
    # 处理命令并发送回复
    response = handle_command(command, args, chat_id)
    send_message(response, chat_id)


def get_token_status_message() -> str:
    """获取token状态消息"""
    try:
        from src.core import XHSToYouTube
        
        # 创建核心实例
        tool = XHSToYouTube()
        
        # 检查凭证状态
        statuses = tool.check_credentials()
        
        lines = [
            "🔐 *凭证状态检查*",
            "",
        ]
        
        # 检查各个凭证
        for key, status in statuses.items():
            if status.valid:
                icon = "✅"
                status_text = "正常"
            else:
                icon = "❌" if not status.exists else "⚠️"
                status_text = status.message
            
            lines.append(f"{icon} *{status.name}*")
            lines.append(f"   状态: {status_text}")
            if status.exists:
                lines.append(f"   路径: {status.path}")
            lines.append("")
        
        # 添加操作提示
        if any(not status.valid for status in statuses.values()):
            lines.append("💡 *提示:*")
            lines.append("使用 /update_token 重新授权 YouTube")
            lines.append("使用 /help 查看其他命令")
        else:
            lines.append("✨ 所有凭证状态正常！")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"❌ 检查凭证状态失败: {e}\n请检查配置文件和日志。"


def handle_update_token_command() -> str:
    """处理更新token命令"""
    try:
        from src.core import XHSToYouTube
        
        # 创建核心实例
        tool = XHSToYouTube()
        
        # 获取授权URL
        success, auth_url = tool.get_authorization_url()
        
        if success:
            return f"""🔐 *YouTube 授权更新*

请按以下步骤完成授权:

1️⃣ 点击授权链接:
{auth_url}

2️⃣ 登录您的Google账号
3️⃣ 允许应用访问权限
4️⃣ 复制页面显示的授权码
5️⃣ 运行: `xhs2yt update --token` 并输入授权码

💡 *提示:*
• 如果链接无法点击，请复制到浏览器打开
• 授权完成后，使用 /token_status 检查状态
• 授权码是一次性的，请尽快使用"""
        else:
            return f"❌ 获取授权链接失败: {auth_url}"
        
    except Exception as e:
        return f"❌ 更新授权失败: {e}\n请检查网络连接和配置文件。"


def run_bot():
    """运行 Bot"""
    load_bot_config()
    
    if not BOT_TOKEN or not CHAT_ID:
        print("错误: 未配置 Telegram Bot Token 或 Chat ID")
        return
    
    print(f"Bot 启动中...")
    print(f"Chat ID: {CHAT_ID}")
    print(f"轮询间隔: {POLLING_INTERVAL}秒")
    
    # 发送启动通知
    send_message("🤖 Bot 已启动\n使用 /help 查看可用命令")
    
    # 开始轮询
    while True:
        try:
            updates = get_updates(offset=LAST_UPDATE_ID)
            for update in updates:
                process_update(update)
        except Exception as e:
            print(f"轮询错误: {e}")
        
        time.sleep(POLLING_INTERVAL)


if __name__ == "__main__":
    run_bot()
