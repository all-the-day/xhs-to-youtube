"""
小红书到 YouTube 视频搬运工具
"""

__version__ = "1.5.0"

from src.models import CredentialStatus, UploadRecord
from src.config import (
    SCRIPT_DIR,
    COOKIES_FILE,
    CREDENTIALS_FILE,
    TOKEN_FILE,
    VIDEOS_DIR,
    UPLOADED_FILE,
    VIDEO_LIST_FILE,
    CONFIG_FILE,
    SCOPES,
    DAILY_UPLOAD_LIMIT,
)
from src.core import XHSToYouTube

__all__ = [
    "XHSToYouTube",
    "CredentialStatus",
    "UploadRecord",
    "SCRIPT_DIR",
    "COOKIES_FILE",
    "CREDENTIALS_FILE",
    "TOKEN_FILE",
    "VIDEOS_DIR",
    "UPLOADED_FILE",
    "VIDEO_LIST_FILE",
    "CONFIG_FILE",
    "SCOPES",
    "DAILY_UPLOAD_LIMIT",
]
