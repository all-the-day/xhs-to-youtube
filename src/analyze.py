"""
受众分析模块

基于 YouTube 数据，分析受众画像（地理位置、年龄、性别），
推荐最佳发布时间段和内容建议。
"""

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import (
    DATA_DIR,
    GEO_DATA_DIR,
    TIMEZONE_CACHE_FILE,
    USER_TIMEZONE,
)
from .models import (
    AudienceRegion,
    AudienceCache,
    AudienceInsight,
    AgeGroup,
    GenderData,
    DemographicsData,
    TimeRecommendation,
)


# 国家代码到时区的映射（主要时区）
COUNTRY_TIMEZONE_MAP = {
    # 东亚
    "CN": "UTC+8", "TW": "UTC+8", "HK": "UTC+8", "MO": "UTC+8",
    "JP": "UTC+9", "KR": "UTC+9",
    # 东南亚
    "VN": "UTC+7", "TH": "UTC+7", "KH": "UTC+7", "LA": "UTC+7",
    "MY": "UTC+8", "SG": "UTC+8", "BN": "UTC+8",
    "PH": "UTC+8",
    "ID": "UTC+7",
    "MM": "UTC+6:30",
    # 南亚
    "BD": "UTC+6", "IN": "UTC+5:30", "PK": "UTC+5", "LK": "UTC+5:30",
    "NP": "UTC+5:45",
    # 中亚
    "KZ": "UTC+6", "UZ": "UTC+5",
    # 西亚/中东
    "TR": "UTC+3", "IQ": "UTC+3", "IR": "UTC+3:30", "SA": "UTC+3",
    "AE": "UTC+4", "LB": "UTC+2", "SY": "UTC+3",
    # 欧洲
    "GB": "UTC+0", "DE": "UTC+1", "FR": "UTC+1", "IT": "UTC+1",
    "ES": "UTC+1", "NL": "UTC+1", "PL": "UTC+1", "UA": "UTC+2",
    "GR": "UTC+2", "RO": "UTC+2", "RS": "UTC+1", "RU": "UTC+3",
    # 北美
    "US": "UTC-5", "CA": "UTC-5",
    "MX": "UTC-6",
    # 南美
    "BR": "UTC-3",
    # 非洲
    "EG": "UTC+2", "DZ": "UTC+1", "NG": "UTC+1",
    # 大洋洲
    "AU": "UTC+10", "NZ": "UTC+12",
    # 蒙古
    "MN": "UTC+8",
}


# ==================== 文件查找 ====================

def find_geo_csv_file() -> Optional[Path]:
    """查找地理位置 CSV 文件"""
    for item in GEO_DATA_DIR.iterdir():
        if item.is_dir() and "地理位置" in item.name:
            csv_file = item / "表格数据.csv"
            if csv_file.exists():
                return csv_file
    return None


def find_demographics_csv_file() -> Optional[Path]:
    """查找年龄/性别 CSV 文件"""
    for item in GEO_DATA_DIR.iterdir():
        if item.is_dir() and ("年龄" in item.name or "性别" in item.name):
            csv_file = item / "表格数据.csv"
            if csv_file.exists():
                return csv_file
    return None


def calculate_file_md5(file_path: Path) -> str:
    """计算文件 MD5 哈希值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


# ==================== 地理位置解析 ====================

def parse_geo_csv(csv_path: Path) -> list[AudienceRegion]:
    """解析地理位置 CSV 文件"""
    regions = []
    total_views = 0
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        for row in rows:
            country_code = row.get("地理位置", "").strip()
            if country_code and country_code != "总计":
                try:
                    views = int(row.get("观看次数", 0))
                    total_views += views
                except ValueError:
                    continue
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country_code = row.get("地理位置", "").strip()
            if country_code and country_code != "总计":
                try:
                    views = int(row.get("观看次数", 0))
                    weight = views / total_views if total_views > 0 else 0
                    timezone = COUNTRY_TIMEZONE_MAP.get(country_code, "UTC+0")
                    
                    regions.append(AudienceRegion(
                        code=country_code,
                        views=views,
                        weight=round(weight, 4),
                        timezone=timezone,
                    ))
                except ValueError:
                    continue
    
    regions.sort(key=lambda x: x.views, reverse=True)
    return regions


# ==================== 年龄/性别解析 ====================

def parse_demographics_csv(csv_path: Path) -> DemographicsData:
    """
    解析年龄/性别 CSV 文件
    
    CSV 格式：
    观看者年龄,观看者性别,观看次数 (%),观看时长（小时） (%)
    13–17 岁,女,0.57,0.49
    13–17 岁,男,0.82,0.67
    ...
    """
    age_data: dict[str, dict] = {}  # age_range -> {views_percent, watch_time_percent}
    gender_data: dict[str, dict] = {}  # gender -> {views_percent, watch_time_percent}
    breakdown = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            age_range = row.get("观看者年龄", "").strip()
            gender = row.get("观看者性别", "").strip()
            
            try:
                views_percent = float(row.get("观看次数 (%)", 0))
                watch_time_percent = float(row.get("观看时长（小时） (%)", 0))
            except ValueError:
                continue
            
            # 记录交叉数据
            breakdown.append({
                "age_range": age_range,
                "gender": gender,
                "views_percent": views_percent,
                "watch_time_percent": watch_time_percent,
            })
            
            # 汇总年龄数据
            if age_range not in age_data:
                age_data[age_range] = {"views_percent": 0, "watch_time_percent": 0}
            age_data[age_range]["views_percent"] += views_percent
            age_data[age_range]["watch_time_percent"] += watch_time_percent
            
            # 汇总性别数据
            if gender not in gender_data:
                gender_data[gender] = {"views_percent": 0, "watch_time_percent": 0}
            gender_data[gender]["views_percent"] += views_percent
            gender_data[gender]["watch_time_percent"] += watch_time_percent
    
    # 转换为数据类
    age_groups = [
        AgeGroup(
            age_range=age,
            views_percent=round(data["views_percent"], 2),
            watch_time_percent=round(data["watch_time_percent"], 2),
        )
        for age, data in age_data.items()
    ]
    
    genders = [
        GenderData(
            gender=gender,
            views_percent=round(data["views_percent"], 2),
            watch_time_percent=round(data["watch_time_percent"], 2),
        )
        for gender, data in gender_data.items()
    ]
    
    # 按观看量排序
    age_groups.sort(key=lambda x: x.views_percent, reverse=True)
    genders.sort(key=lambda x: x.views_percent, reverse=True)
    
    return DemographicsData(
        age_groups=age_groups,
        genders=genders,
        age_gender_breakdown=breakdown,
    )


# ==================== 时间推荐计算 ====================

# 地区工作文化特征
REGION_WORK_CULTURE = {
    # 东亚：高强度工作，晚下班
    "CN": {"work_end": 18, "dinner_end": 20, "prime_time": (20, 23)},
    "TW": {"work_end": 18, "dinner_end": 19, "prime_time": (19, 23)},
    "JP": {"work_end": 19, "dinner_end": 20, "prime_time": (21, 24)},
    "KR": {"work_end": 18, "dinner_end": 20, "prime_time": (20, 23)},
    "HK": {"work_end": 18, "dinner_end": 20, "prime_time": (20, 23)},
    # 东南亚：相对轻松
    "VN": {"work_end": 17, "dinner_end": 19, "prime_time": (19, 22)},
    "TH": {"work_end": 17, "dinner_end": 19, "prime_time": (19, 22)},
    "MY": {"work_end": 17, "dinner_end": 19, "prime_time": (20, 23)},
    "SG": {"work_end": 18, "dinner_end": 20, "prime_time": (20, 23)},
    "ID": {"work_end": 17, "dinner_end": 19, "prime_time": (19, 22)},
    "PH": {"work_end": 17, "dinner_end": 19, "prime_time": (20, 23)},
    # 南亚
    "IN": {"work_end": 18, "dinner_end": 20, "prime_time": (21, 24)},
    # 欧美
    "US": {"work_end": 17, "dinner_end": 19, "prime_time": (19, 23)},
    "CA": {"work_end": 17, "dinner_end": 19, "prime_time": (19, 23)},
    "GB": {"work_end": 17, "dinner_end": 19, "prime_time": (19, 23)},
    "DE": {"work_end": 17, "dinner_end": 19, "prime_time": (19, 23)},
}

# 年龄段对应的生活规律
AGE_LIFESTYLE = {
    "13–17 岁": {"type": "student", "prime_time": (16, 22), "weight": 0.5},
    "18–24 岁": {"type": "student_young", "prime_time": (18, 24), "weight": 0.7},
    "25–34 岁": {"type": "worker", "prime_time": (20, 24), "weight": 1.0},
    "35–44 岁": {"type": "worker_family", "prime_time": (20, 23), "weight": 1.0},
    "45–54 岁": {"type": "mid_age", "prime_time": (19, 22), "weight": 0.8},
    "55–64 岁": {"type": "older", "prime_time": (18, 22), "weight": 0.6},
    "65 岁以上": {"type": "senior", "prime_time": (10, 12), "weight": 0.4},
}


def calculate_best_upload_time(
    regions: list[AudienceRegion],
    demographics: Optional[DemographicsData] = None,
    user_timezone: str = USER_TIMEZONE,
) -> TimeRecommendation:
    """
    计算最佳上传时间
    
    综合考虑：
    1. 受众地理位置 → 主要时区
    2. 受众年龄分布 → 作息规律（上班族/学生/退休）
    3. 地区工作文化 → 下班时间、晚间休闲时段
    
    优先级：
    - 上班族(25-44岁): 晚间 20:00-23:00 最佳
    - 学生(13-24岁): 下午 16:00-22:00 活跃
    - 退休人群(65+): 上午 10:00-12:00 活跃
    """
    if not regions:
        return TimeRecommendation(
            optimal_time="20:00-22:00",
            secondary_time="14:00-16:00",
            user_timezone=user_timezone,
            primary_tz_weight=0,
            reason="暂无数据，使用默认推荐（晚间黄金档）",
        )
    
    # 1. 计算主要受众时区
    tz_weights: dict[str, float] = {}
    for region in regions:
        tz = region.timezone
        tz_weights[tz] = tz_weights.get(tz, 0) + region.weight
    
    primary_tz = max(tz_weights.items(), key=lambda x: x[1])
    primary_tz_name = primary_tz[0]
    primary_tz_weight = primary_tz[1]
    
    # 2. 分析年龄分布，确定受众类型
    audience_type = "worker"  # 默认上班族
    if demographics and demographics.age_groups:
        # 找出主要年龄段
        top_age = demographics.age_groups[0] if demographics.age_groups else None
        if top_age:
            age_range = top_age.age_range
            if age_range in AGE_LIFESTYLE:
                audience_type = AGE_LIFESTYLE[age_range]["type"]
    
    # 3. 获取主要地区的工作文化
    top_region_code = regions[0].code if regions else "CN"
    work_culture = REGION_WORK_CULTURE.get(top_region_code, REGION_WORK_CULTURE["CN"])
    
    # 4. 根据受众类型确定黄金时段
    if audience_type in ["worker", "worker_family"]:
        # 上班族：下班后晚餐结束到睡觉前
        prime_start = work_culture["prime_time"][0]
        prime_end = work_culture["prime_time"][1]
        # 黄金时段：晚间休闲
        optimal_time = f"{prime_start}:00-{prime_end}:00"
        # 次选：午休时段
        secondary_time = "12:00-13:00"
    elif audience_type in ["student", "student_young"]:
        # 学生：下午放学后
        optimal_time = "16:00-22:00"
        secondary_time = "12:00-14:00"
    elif audience_type == "senior":
        # 退休人群：上午
        optimal_time = "10:00-12:00"
        secondary_time = "14:00-16:00"
    else:
        # 默认
        optimal_time = f"{work_culture['prime_time'][0]}:00-{work_culture['prime_time'][1]}:00"
        secondary_time = "14:00-16:00"
    
    # 5. 时区转换（转换为用户本地时间）
    user_offset = parse_timezone_offset(user_timezone)
    primary_offset = parse_timezone_offset(primary_tz_name)
    offset_diff = user_offset - primary_offset
    
    # 解析时间段并转换
    optimal_converted = convert_time_range(optimal_time, offset_diff)
    secondary_converted = convert_time_range(secondary_time, offset_diff)
    
    # 6. 生成推荐原因
    top_regions = regions[:3]
    top_info = ", ".join([f"{r.code}({int(r.weight*100)}%)" for r in top_regions])
    
    audience_desc = {
        "worker": "上班族",
        "worker_family": "上班族/家庭",
        "student": "学生",
        "student_young": "年轻学生",
        "older": "中年群体",
        "senior": "退休群体",
    }.get(audience_type, "上班族")
    
    reason = f"受众: {audience_desc}，地区: {top_info}"
    
    return TimeRecommendation(
        optimal_time=optimal_converted,
        secondary_time=secondary_converted,
        user_timezone=user_timezone,
        primary_tz_weight=round(primary_tz_weight, 2),
        reason=reason,
    )


def convert_time_range(time_range: str, offset_diff: float) -> str:
    """将时间段从受众时区转换为用户时区"""
    try:
        parts = time_range.split("-")
        start = int(parts[0].split(":")[0])
        end = int(parts[1].split(":")[0])
        
        # 转换
        start = int((start - offset_diff) % 24)
        end = int((end - offset_diff) % 24)
        
        return f"{start:02d}:00-{end:02d}:00"
    except (IndexError, ValueError, TypeError):
        return time_range


def parse_timezone_offset(tz_str: str) -> float:
    """解析时区偏移量"""
    if tz_str.startswith("UTC"):
        offset_str = tz_str[3:]
        if ":" in offset_str:
            parts = offset_str.split(":")
            hours = int(parts[0])
            minutes = int(parts[1]) if len(parts) > 1 else 0
            sign = 1 if hours >= 0 else -1
            return hours + sign * minutes / 60
        else:
            return float(offset_str) if offset_str else 0
    else:
        timezone_offsets = {
            "Asia/Shanghai": 8,
            "Asia/Taipei": 8,
            "Asia/Hong_Kong": 8,
            "Asia/Tokyo": 9,
            "Asia/Seoul": 9,
            "Asia/Singapore": 8,
            "Asia/Kuala_Lumpur": 8,
            "Asia/Bangkok": 7,
            "Asia/Ho_Chi_Minh": 7,
            "Asia/Jakarta": 7,
            "America/New_York": -5,
            "America/Los_Angeles": -8,
            "Europe/London": 0,
            "Europe/Paris": 1,
            "Europe/Berlin": 1,
        }
        return timezone_offsets.get(tz_str, 0)


def format_time_range(start: float, end: float) -> str:
    """格式化时间范围"""
    return f"{int(start):02d}:00-{int(end):02d}:00"


# ==================== 受众洞察计算 ====================

def calculate_audience_insight(
    demographics: Optional[DemographicsData],
    regions: list[AudienceRegion],
) -> Optional[AudienceInsight]:
    """计算受众洞察"""
    if not demographics or not demographics.age_groups:
        return None
    
    # 主要年龄段
    primary_age = demographics.age_groups[0]
    
    # 性别比例
    male_percent = 0
    female_percent = 0
    for g in demographics.genders:
        if g.gender == "男":
            male_percent = g.views_percent
        elif g.gender == "女":
            female_percent = g.views_percent
    
    dominant_gender = "男" if male_percent > female_percent else "女"
    gender_ratio = f"男{int(male_percent)}% 女{int(female_percent)}%"
    
    # 内容建议
    content_suggestion = generate_content_suggestion(
        primary_age.age_range,
        dominant_gender,
        regions[:3] if regions else [],
    )
    
    return AudienceInsight(
        primary_age_group=primary_age.age_range,
        primary_age_percent=primary_age.views_percent,
        gender_ratio=gender_ratio,
        dominant_gender=dominant_gender,
        content_suggestion=content_suggestion,
    )


def generate_content_suggestion(
    age_range: str,
    dominant_gender: str,
    top_regions: list[AudienceRegion],
) -> str:
    """生成内容建议"""
    suggestions = []
    
    # 年龄建议
    if "13" in age_range or "17" in age_range:
        suggestions.append("年轻化")
    elif "18" in age_range or "24" in age_range:
        suggestions.append("活力时尚")
    elif "25" in age_range or "34" in age_range:
        suggestions.append("职场/生活")
    elif "35" in age_range or "44" in age_range:
        suggestions.append("成熟稳重")
    else:
        suggestions.append("稳健")
    
    # 性别建议
    if dominant_gender == "女":
        suggestions.append("细腻情感")
    else:
        suggestions.append("理性实用")
    
    # 地区建议
    if top_regions:
        region_codes = [r.code for r in top_regions]
        if "TW" in region_codes or "HK" in region_codes:
            suggestions.append("繁体字幕")
        if "JP" in region_codes:
            suggestions.append("日文字幕可选")
    
    return "、".join(suggestions)


# ==================== 缓存管理 ====================

def load_audience_cache() -> Optional[AudienceCache]:
    """加载受众分析缓存"""
    if not TIMEZONE_CACHE_FILE.exists():
        return None
    
    try:
        with open(TIMEZONE_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        regions = [
            AudienceRegion(**r) for r in data.get("regions", [])
        ]
        
        demographics = None
        if data.get("demographics"):
            demo_data = data["demographics"]
            demographics = DemographicsData(
                age_groups=[AgeGroup(**a) for a in demo_data.get("age_groups", [])],
                genders=[GenderData(**g) for g in demo_data.get("genders", [])],
                age_gender_breakdown=demo_data.get("age_gender_breakdown", []),
            )
        
        recommendation = None
        if data.get("recommendation"):
            recommendation = TimeRecommendation(**data["recommendation"])
        
        insight = None
        if data.get("insight"):
            insight = AudienceInsight(**data["insight"])
        
        return AudienceCache(
            geo_source_file=data.get("geo_source_file", ""),
            geo_source_mtime=data.get("geo_source_mtime", 0),
            geo_source_md5=data.get("geo_source_md5", ""),
            demo_source_file=data.get("demo_source_file", ""),
            demo_source_mtime=data.get("demo_source_mtime", 0),
            demo_source_md5=data.get("demo_source_md5", ""),
            analyzed_at=data.get("analyzed_at", ""),
            total_views=data.get("total_views", 0),
            regions=regions,
            demographics=demographics,
            recommendation=recommendation,
            insight=insight,
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def save_audience_cache(cache: AudienceCache) -> None:
    """保存受众分析缓存"""
    data = {
        "geo_source_file": cache.geo_source_file,
        "geo_source_mtime": cache.geo_source_mtime,
        "geo_source_md5": cache.geo_source_md5,
        "demo_source_file": cache.demo_source_file,
        "demo_source_mtime": cache.demo_source_mtime,
        "demo_source_md5": cache.demo_source_md5,
        "analyzed_at": cache.analyzed_at,
        "total_views": cache.total_views,
        "regions": [
            {"code": r.code, "views": r.views, "weight": r.weight, "timezone": r.timezone}
            for r in cache.regions
        ],
        "demographics": None,
        "recommendation": None,
        "insight": None,
    }
    
    if cache.demographics:
        data["demographics"] = {
            "age_groups": [
                {"age_range": a.age_range, "views_percent": a.views_percent, "watch_time_percent": a.watch_time_percent}
                for a in cache.demographics.age_groups
            ],
            "genders": [
                {"gender": g.gender, "views_percent": g.views_percent, "watch_time_percent": g.watch_time_percent}
                for g in cache.demographics.genders
            ],
            "age_gender_breakdown": cache.demographics.age_gender_breakdown,
        }
    
    if cache.recommendation:
        data["recommendation"] = {
            "optimal_time": cache.recommendation.optimal_time,
            "secondary_time": cache.recommendation.secondary_time,
            "user_timezone": cache.recommendation.user_timezone,
            "primary_tz_weight": cache.recommendation.primary_tz_weight,
            "reason": cache.recommendation.reason,
        }
    
    if cache.insight:
        data["insight"] = {
            "primary_age_group": cache.insight.primary_age_group,
            "primary_age_percent": cache.insight.primary_age_percent,
            "gender_ratio": cache.insight.gender_ratio,
            "dominant_gender": cache.insight.dominant_gender,
            "content_suggestion": cache.insight.content_suggestion,
        }
    
    with open(TIMEZONE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==================== 主分析函数 ====================

def analyze_and_cache(
    force: bool = False,
    log_callback=None,
) -> Optional[AudienceCache]:
    """
    分析所有受众数据并缓存结果
    """
    def log(msg: str):
        if log_callback:
            log_callback(msg)
    
    # 加载现有缓存
    cache = load_audience_cache()
    if not cache:
        cache = AudienceCache()
    
    need_save = False
    
    # ========== 分析地理位置数据 ==========
    geo_file = find_geo_csv_file()
    if geo_file:
        log(f"🌍 找到地理位置数据: {geo_file.parent.name}")
        
        current_mtime = geo_file.stat().st_mtime
        current_md5 = calculate_file_md5(geo_file)
        
        # 检查是否需要重新分析
        geo_changed = (
            cache.geo_source_file != str(geo_file) or
            abs(cache.geo_source_mtime - current_mtime) >= 1 or
            cache.geo_source_md5 != current_md5
        )
        
        if geo_changed or force:
            log("   正在分析地理位置数据...")
            regions = parse_geo_csv(geo_file)
            if regions:
                cache.geo_source_file = str(geo_file)
                cache.geo_source_mtime = current_mtime
                cache.geo_source_md5 = current_md5
                cache.regions = regions
                cache.total_views = sum(r.views for r in regions)
                # 时间推荐在后面统一计算（需要结合 demographics）
                log(f"   ✅ 已分析 {len(regions)} 个地区")
                need_save = True
        else:
            log("   ✅ 使用缓存的地理位置数据")
    else:
        log("⚠️  未找到地理位置数据文件")
    
    # ========== 分析年龄/性别数据 ==========
    demo_file = find_demographics_csv_file()
    if demo_file:
        log(f"👥 找到年龄/性别数据: {demo_file.parent.name}")
        
        current_mtime = demo_file.stat().st_mtime
        current_md5 = calculate_file_md5(demo_file)
        
        demo_changed = (
            cache.demo_source_file != str(demo_file) or
            abs(cache.demo_source_mtime - current_mtime) >= 1 or
            cache.demo_source_md5 != current_md5
        )
        
        if demo_changed or force:
            log("   正在分析年龄/性别数据...")
            demographics = parse_demographics_csv(demo_file)
            cache.demo_source_file = str(demo_file)
            cache.demo_source_mtime = current_mtime
            cache.demo_source_md5 = current_md5
            cache.demographics = demographics
            log(f"   ✅ 已分析 {len(demographics.age_groups)} 个年龄段")
            need_save = True
        else:
            log("   ✅ 使用缓存的年龄/性别数据")
    else:
        log("⚠️  未找到年龄/性别数据文件")
    
    # ========== 重新计算时间推荐（结合地理位置和年龄） ==========
    if cache.regions:
        cache.recommendation = calculate_best_upload_time(
            cache.regions, 
            cache.demographics
        )
        need_save = True
    
    # ========== 计算受众洞察 ==========
    if cache.regions or cache.demographics:
        cache.insight = calculate_audience_insight(cache.demographics, cache.regions)
        need_save = True
    
    # ========== 保存缓存 ==========
    if need_save:
        cache.analyzed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_audience_cache(cache)
        log("✅ 分析结果已缓存")
    
    return cache if (cache.regions or cache.demographics) else None


# ==================== 便捷函数 ====================

def get_time_recommendation() -> Optional[TimeRecommendation]:
    """获取时间推荐"""
    cache = load_audience_cache()
    if cache and cache.recommendation:
        return cache.recommendation
    
    cache = analyze_and_cache()
    return cache.recommendation if cache else None


def format_audience_report(
    cache: AudienceCache,
    current_hour: Optional[int] = None,
) -> str:
    """格式化完整的受众画像报告"""
    lines = [
        "",
        "📊 受众画像分析",
        "━" * 50,
    ]
    
    # 地理位置分布
    if cache.regions:
        lines.append("")
        lines.append("🌍 地理位置分布 (Top 5):")
        for i, r in enumerate(cache.regions[:5]):
            lines.append(f"  {i+1}. {r.code}: {r.weight*100:.1f}% [{r.timezone}]")
    
    # 年龄分布
    if cache.demographics and cache.demographics.age_groups:
        lines.append("")
        lines.append("👥 年龄分布:")
        for a in cache.demographics.age_groups[:5]:
            bar = "█" * int(a.views_percent / 5) + "░" * (20 - int(a.views_percent / 5))
            lines.append(f"  {a.age_range}: {a.views_percent:.0f}% {bar}")
    
    # 性别分布
    if cache.demographics and cache.demographics.genders:
        lines.append("")
        lines.append("👤 性别分布:")
        for g in cache.demographics.genders:
            bar = "█" * int(g.views_percent / 5) + "░" * (20 - int(g.views_percent / 5))
            lines.append(f"  {g.gender}: {g.views_percent:.0f}% {bar}")
    
    # 发布时间建议
    if cache.recommendation:
        lines.append("")
        lines.append("⏰ 发布时间建议:")
        
        if current_hour is not None:
            lines.append(f"  当前时间: {current_hour:02d}:00 (北京时间)")
            
            optimal_parts = cache.recommendation.optimal_time.split("-")
            secondary_parts = cache.recommendation.secondary_time.split("-")
            optimal_start = int(optimal_parts[0].split(":")[0])
            optimal_end = int(optimal_parts[1].split(":")[0])
            secondary_start = int(secondary_parts[0].split(":")[0])
            secondary_end = int(secondary_parts[1].split(":")[0])
            
            in_optimal = optimal_start <= current_hour < optimal_end
            in_secondary = secondary_start <= current_hour < secondary_end
            
            if in_optimal:
                lines.append("  ✅ 当前处于黄金时段！")
            elif in_secondary:
                lines.append("  👍 当前处于次选时段")
            else:
                lines.append("  ⚠️  当前不在推荐时段")
        
        lines.append(f"  🎯 黄金时段: {cache.recommendation.optimal_time}")
        lines.append(f"  📊 次选时段: {cache.recommendation.secondary_time}")
    
    # 受众洞察
    if cache.insight:
        lines.append("")
        lines.append("💡 受众洞察:")
        lines.append(f"  主要年龄: {cache.insight.primary_age_group} ({cache.insight.primary_age_percent:.0f}%)")
        lines.append(f"  性别比例: {cache.insight.gender_ratio}")
        lines.append(f"  内容建议: {cache.insight.content_suggestion}")
    
    lines.append("━" * 50)
    
    return "\n".join(lines)


def format_time_suggestion(
    recommendation: TimeRecommendation,
    current_hour: Optional[int] = None,
) -> str:
    """格式化时间建议提示（用于上传时显示）"""
    lines = [
        "",
        "⏰  发布时间建议",
        "━" * 40,
    ]
    
    if current_hour is not None:
        lines.append(f"  当前时间: {current_hour:02d}:00 (北京时间)")
        lines.append("")
        
        optimal_parts = recommendation.optimal_time.split("-")
        secondary_parts = recommendation.secondary_time.split("-")
        optimal_start = int(optimal_parts[0].split(":")[0])
        optimal_end = int(optimal_parts[1].split(":")[0])
        secondary_start = int(secondary_parts[0].split(":")[0])
        secondary_end = int(secondary_parts[1].split(":")[0])
        
        in_optimal = optimal_start <= current_hour < optimal_end
        in_secondary = secondary_start <= current_hour < secondary_end
        
        if in_optimal:
            lines.append("  ✅ 当前处于黄金时段！")
        elif in_secondary:
            lines.append("  👍 当前处于次选时段")
        else:
            lines.append("  ⚠️  当前不在推荐时段")
    
    lines.extend([
        "",
        f"  🎯 黄金时段: {recommendation.optimal_time} (建议)",
        f"  📊 次选时段: {recommendation.secondary_time}",
        "",
        f"  {recommendation.reason}",
        "━" * 40,
    ])
    
    return "\n".join(lines)


def is_good_upload_time(current_hour: Optional[int] = None) -> tuple[bool, str]:
    """检查当前是否是好的上传时间"""
    if current_hour is None:
        current_hour = datetime.now().hour
    
    recommendation = get_time_recommendation()
    if not recommendation:
        return True, "暂无时间推荐数据"
    
    optimal_parts = recommendation.optimal_time.split("-")
    secondary_parts = recommendation.secondary_time.split("-")
    optimal_start = int(optimal_parts[0].split(":")[0])
    optimal_end = int(optimal_parts[1].split(":")[0])
    secondary_start = int(secondary_parts[0].split(":")[0])
    secondary_end = int(secondary_parts[1].split(":")[0])
    
    in_optimal = optimal_start <= current_hour < optimal_end
    in_secondary = secondary_start <= current_hour < secondary_end
    
    if in_optimal:
        return True, f"黄金时段 {recommendation.optimal_time}"
    elif in_secondary:
        return True, f"次选时段 {recommendation.secondary_time}"
    else:
        return False, f"建议在 {recommendation.optimal_time} 或 {recommendation.secondary_time} 发布"


# ==================== 向后兼容 ====================

# 保持旧函数名兼容
TimezoneCache = AudienceCache
load_timezone_cache = load_audience_cache
save_timezone_cache = save_audience_cache
