"""
配置常量
"""

from pathlib import Path

# 基础路径
SCRIPT_DIR = Path(__file__).parent.parent.absolute()

# 敏感文件
COOKIES_FILE = SCRIPT_DIR / "cookies.txt"
CREDENTIALS_FILE = SCRIPT_DIR / "credentials.json"
TOKEN_FILE = SCRIPT_DIR / "token.json"

# 数据目录
DATA_DIR = SCRIPT_DIR / "data"
VIDEOS_DIR = SCRIPT_DIR / "cache" / "videos"

# 数据文件
UPLOADED_FILE = DATA_DIR / "uploaded.json"
VIDEO_LIST_FILE = DATA_DIR / "video_list.json"
CONFIG_FILE = SCRIPT_DIR / "config" / "config.json"

# 时区分析相关
GEO_DATA_DIR = DATA_DIR  # 地理位置数据目录（支持多个子目录）
TIMEZONE_CACHE_FILE = DATA_DIR / "timezone_cache.json"
USER_TIMEZONE = "Asia/Shanghai"  # 默认用户时区

# YouTube API 权限范围
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# 每日上传限制
DAILY_UPLOAD_LIMIT = 10
