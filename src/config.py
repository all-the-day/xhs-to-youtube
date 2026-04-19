"""
配置常量
"""

import json
from pathlib import Path
from typing import Any

# 基础路径
SCRIPT_DIR = Path(__file__).parent.parent.absolute()

# 敏感文件
COOKIES_FILE = SCRIPT_DIR / "cookies.txt"
CREDENTIALS_FILE = SCRIPT_DIR / "credentials.json"
TOKEN_FILE = SCRIPT_DIR / "token.json"

# 数据目录
DATA_DIR = SCRIPT_DIR / "data"
VIDEOS_DIR = SCRIPT_DIR / "cache" / "videos"
LOGS_DIR = SCRIPT_DIR / "logs"

# 数据文件
UPLOADED_FILE = DATA_DIR / "uploaded.json"
VIDEO_LIST_FILE = DATA_DIR / "video_list.json"
CONFIG_FILE = SCRIPT_DIR / "config" / "config.json"
SCHEDULE_LOG_FILE = LOGS_DIR / "schedule.log"

# 时区分析相关
GEO_DATA_DIR = DATA_DIR  # 地理位置数据目录（支持多个子目录）
TIMEZONE_CACHE_FILE = DATA_DIR / "timezone_cache.json"
USER_TIMEZONE = "Asia/Shanghai"  # 默认用户时区

# YouTube API 权限范围
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# 每日上传限制
DAILY_UPLOAD_LIMIT = 10

# 默认调度配置
DEFAULT_SCHEDULE_CONFIG = {
    "tasks": [
        {"time": "08:00", "limit": 3, "enabled": True, "description": "早间上传"},
        {"time": "12:00", "limit": 3, "enabled": True, "description": "午间上传"},
        {"time": "20:00", "limit": 4, "enabled": True, "description": "晚间上传"},
    ],
    "default_limit": 3,
    "log_file": "logs/schedule.log",
    "notification": {
        "enabled": False,
        "feishu_webhook": "",
        "notify_on_success": False,
        "notify_on_failure": True,
    },
}

DEFAULT_WEB_CONFIG = {
    "enabled": False,
    "username": "",
    "password": "",
    "csrf_enabled": False,
    "secret_key": "",
    "realm": "xhs-to-youtube web console",
}


def load_config() -> dict[str, Any]:
    """加载配置文件"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"proxies": {}}


def load_schedule_config() -> dict[str, Any]:
    """加载调度配置"""
    config = load_config()
    schedule_config = config.get("schedule", {})
    
    # 合并默认配置
    result = DEFAULT_SCHEDULE_CONFIG.copy()
    result.update(schedule_config)
    
    return result


def load_web_config() -> dict[str, Any]:
    """加载 Web 控制台配置"""
    config = load_config()
    web_config = config.get("web", {})

    result = DEFAULT_WEB_CONFIG.copy()
    result.update(web_config)
    return result


def get_schedule_task_for_time(time_str: str) -> dict[str, Any] | None:
    """根据时间字符串获取对应的调度任务
    
    Args:
        time_str: 时间字符串，格式为 "HH:MM"
    
    Returns:
        匹配的任务配置，如果没有匹配则返回 None
    """
    config = load_schedule_config()
    tasks = config.get("tasks", [])
    
    for task in tasks:
        if task.get("time") == time_str and task.get("enabled", True):
            return task
    
    return None


def ensure_logs_dir() -> None:
    """确保日志目录存在"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
