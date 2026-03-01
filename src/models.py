"""
数据类定义
"""

from dataclasses import dataclass


@dataclass
class CredentialStatus:
    """凭证状态"""
    name: str
    exists: bool
    valid: bool
    message: str
    path: str


@dataclass
class UploadRecord:
    """上传记录"""
    note_id: str
    youtube_id: str
    youtube_url: str
    title: str
    uploaded_at: str
