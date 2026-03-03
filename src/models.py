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
    # 时间分析字段
    upload_hour: Optional[int] = None         # 上传小时 (0-23)
    time_slot: Optional[str] = None           # 时间段标签 (黄金时段/次选时段/非推荐时段)
    recommendation_followed: Optional[bool] = None  # 是否遵循推荐时段


@dataclass
class AudienceRegion:
    """受众地区数据"""
    code: str           # 国家代码 (e.g., "TW", "JP")
    views: int          # 观看次数
    weight: float       # 权重占比 (0-1)
    timezone: str       # 时区偏移 (e.g., "UTC+8")


@dataclass
class AgeGroup:
    """年龄分组数据"""
    age_range: str      # 年龄段 (e.g., "18-24 岁")
    views_percent: float  # 观看次数占比
    watch_time_percent: float  # 观看时长占比


@dataclass
class GenderData:
    """性别数据"""
    gender: str         # 性别 (e.g., "女", "男")
    views_percent: float  # 观看次数占比
    watch_time_percent: float  # 观看时长占比


@dataclass
class DemographicsData:
    """人口统计数据（年龄+性别）"""
    age_groups: list[AgeGroup] = field(default_factory=list)
    genders: list[GenderData] = field(default_factory=list)
    # 组合数据：年龄+性别交叉
    age_gender_breakdown: list[dict] = field(default_factory=list)


@dataclass
class TimeRecommendation:
    """时间推荐结果"""
    optimal_time: str           # 最佳发布时间段 (e.g., "20:00-22:00")
    secondary_time: str         # 次选时间段
    user_timezone: str          # 用户所在时区
    primary_tz_weight: float    # 主要时区权重占比
    reason: str                 # 推荐原因


@dataclass
class AudienceInsight:
    """受众洞察"""
    primary_age_group: str      # 主要年龄段
    primary_age_percent: float  # 主要年龄段占比
    gender_ratio: str           # 性别比例 (e.g., "男60% 女40%")
    dominant_gender: str        # 主导性别
    content_suggestion: str     # 内容风格建议


@dataclass
class AudienceCache:
    """受众分析缓存"""
    # 地理位置数据
    geo_source_file: str = ""
    geo_source_mtime: float = 0
    geo_source_md5: str = ""
    
    # 人口统计数据
    demo_source_file: str = ""
    demo_source_mtime: float = 0
    demo_source_md5: str = ""
    
    analyzed_at: str = ""
    total_views: int = 0
    
    # 分析结果
    regions: list[AudienceRegion] = field(default_factory=list)
    demographics: Optional[DemographicsData] = None
    recommendation: Optional[TimeRecommendation] = None
    insight: Optional[AudienceInsight] = None


# 向后兼容别名
TimezoneCache = AudienceCache
