"""
小红书到 YouTube 视频搬运工具

自动下载小红书视频并上传到 YouTube 频道
支持无水印下载、OAuth 授权、命令行使用
"""

from .core import XHSToYouTube, CredentialStatus
from .core import (
    COOKIES_FILE,
    CREDENTIALS_FILE,
    TOKEN_FILE,
    VIDEOS_DIR,
    SCOPES
)

__version__ = "1.2.0"
__author__ = "XHS to YouTube"
__all__ = [
    "XHSToYouTube",
    "CredentialStatus",
    "COOKIES_FILE",
    "CREDENTIALS_FILE",
    "TOKEN_FILE",
    "VIDEOS_DIR",
    "SCOPES",
]
