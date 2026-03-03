"""
数据类定义
"""

from dataclasses import dataclass, field
from typing import Optional


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


@dataclass
class AudienceRegion:
    """受众地区数据"""
    code: str           # 国家代码 (e.g., "TW", "JP")
    views: int          # 观看次数
    weight: float       # 权重占比 (0-1)
    timezone: str       # 时区偏移 (e.g., "UTC+8")


@dataclass
class TimeRecommendation:
    """时间推荐结果"""
    optimal_time: str           # 最佳发布时间段 (e.g., "20:00-22:00")
    secondary_time: str         # 次选时间段
    user_timezone: str          # 用户所在时区
    primary_tz_weight: float    # 主要时区权重占比
    reason: str                 # 推荐原因


@dataclass
class TimezoneCache:
    """时区分析缓存"""
    source_file: str                    # 源 CSV 文件路径
    source_mtime: float                 # 源文件修改时间戳
    source_md5: str                     # 源文件 MD5
    analyzed_at: str                    # 分析时间
    total_views: int                    # 总观看量
    regions: list[AudienceRegion] = field(default_factory=list)
    recommendation: Optional[TimeRecommendation] = None
