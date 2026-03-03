"""
时区分析模块

基于 YouTube 地理位置数据，分析受众时区分布，推荐最佳发布时间段。
"""

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import (
    DATA_DIR,
    GEO_DATA_DIR,
    TIMEZONE_CACHE_FILE,
    USER_TIMEZONE,
)
from .models import AudienceRegion, TimeRecommendation, TimezoneCache


# 国家代码到时区的映射（主要时区）
COUNTRY_TIMEZONE_MAP = {
    # 东亚
    "CN": "UTC+8", "TW": "UTC+8", "HK": "UTC+8", "MO": "UTC+8",
    "JP": "UTC+9", "KR": "UTC+9",
    # 东南亚
    "VN": "UTC+7", "TH": "UTC+7", "KH": "UTC+7", "LA": "UTC+7",
    "MY": "UTC+8", "SG": "UTC+8", "BN": "UTC+8",
    "PH": "UTC+8",
    "ID": "UTC+7",  # 雅加达
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


def find_geo_csv_file() -> Optional[Path]:
    """
    在 data 目录下查找地理位置 CSV 文件
    
    查找规则：寻找包含"表格数据.csv"的子目录
    """
    for item in GEO_DATA_DIR.iterdir():
        if item.is_dir():
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


def parse_geo_csv(csv_path: Path) -> list[AudienceRegion]:
    """
    解析地理位置 CSV 文件
    
    CSV 格式：
    地理位置,观看次数,平均观看时长,观看时长（小时）
    总计,26588,0:00:15,38.5159
    TW,5532,0:00:15,7.4629
    ...
    """
    regions = []
    total_views = 0
    
    # 第一遍：计算总观看量（排除"总计"行）
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country_code = row.get("地理位置", "").strip()
            if country_code and country_code != "总计":
                try:
                    views = int(row.get("观看次数", 0))
                    total_views += views
                except ValueError:
                    continue
    
    # 第二遍：解析各地区数据
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
    
    # 按观看量降序排序
    regions.sort(key=lambda x: x.views, reverse=True)
    return regions


def calculate_best_upload_time(
    regions: list[AudienceRegion],
    user_timezone: str = USER_TIMEZONE,
) -> TimeRecommendation:
    """
    计算最佳上传时间
    
    基于 YouTube 最佳实践：
    - 黄金时段：当地下午 2-4 点（14:00-16:00）
    - 次选时段：当地晚间 8-10 点（20:00-22:00）
    
    逻辑：
    1. 计算各时区的加权观看量
    2. 找出主要受众时区
    3. 将黄金时段转换为用户本地时间
    """
    if not regions:
        return TimeRecommendation(
            optimal_time="14:00-16:00",
            secondary_time="20:00-22:00",
            user_timezone=user_timezone,
            primary_tz_weight=0,
            reason="暂无地理位置数据，使用默认推荐时间",
        )
    
    # 统计各时区的总权重
    tz_weights: dict[str, float] = {}
    for region in regions:
        tz = region.timezone
        tz_weights[tz] = tz_weights.get(tz, 0) + region.weight
    
    # 找出主要时区（权重最大的）
    primary_tz = max(tz_weights.items(), key=lambda x: x[1])
    primary_tz_name = primary_tz[0]
    primary_tz_weight = primary_tz[1]
    
    # 解析用户时区偏移
    user_offset = parse_timezone_offset(user_timezone)
    primary_offset = parse_timezone_offset(primary_tz_name)
    
    # 计算时差（用户时间 = 受众时间 + 时差）
    offset_diff = user_offset - primary_offset
    
    # 将受众黄金时段（14:00-16:00）转换为用户本地时间
    optimal_start = (14 - offset_diff) % 24
    optimal_end = (16 - offset_diff) % 24
    
    # 次选时段（20:00-22:00）
    secondary_start = (20 - offset_diff) % 24
    secondary_end = (22 - offset_diff) % 24
    
    # 格式化时间
    optimal_time = format_time_range(optimal_start, optimal_end)
    secondary_time = format_time_range(secondary_start, secondary_end)
    
    # 生成推荐原因
    top_regions = regions[:3]
    top_info = ", ".join([f"{r.code}({int(r.weight*100)}%)" for r in top_regions])
    reason = f"主要受众: {top_info}，时区: {primary_tz_name}"
    
    return TimeRecommendation(
        optimal_time=optimal_time,
        secondary_time=secondary_time,
        user_timezone=user_timezone,
        primary_tz_weight=round(primary_tz_weight, 2),
        reason=reason,
    )


def parse_timezone_offset(tz_str: str) -> float:
    """
    解析时区偏移量
    
    输入: "UTC+8" 或 "Asia/Shanghai" 或 "UTC+5:30"
    输出: 8.0 或 5.5
    """
    if tz_str.startswith("UTC"):
        # 处理 "UTC+8" 或 "UTC+5:30" 格式
        offset_str = tz_str[3:]  # 去掉 "UTC"
        if ":" in offset_str:
            parts = offset_str.split(":")
            hours = int(parts[0])
            minutes = int(parts[1]) if len(parts) > 1 else 0
            sign = 1 if hours >= 0 else -1
            return hours + sign * minutes / 60
        else:
            return float(offset_str) if offset_str else 0
    else:
        # 处理 IANA 时区名称
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
    start_h = int(start)
    end_h = int(end)
    return f"{start_h:02d}:00-{end_h:02d}:00"


def load_timezone_cache() -> Optional[TimezoneCache]:
    """加载时区缓存"""
    if not TIMEZONE_CACHE_FILE.exists():
        return None
    
    try:
        with open(TIMEZONE_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        regions = [
            AudienceRegion(**r) for r in data.get("regions", [])
        ]
        recommendation = None
        if data.get("recommendation"):
            recommendation = TimeRecommendation(**data["recommendation"])
        
        return TimezoneCache(
            source_file=data["source_file"],
            source_mtime=data["source_mtime"],
            source_md5=data["source_md5"],
            analyzed_at=data["analyzed_at"],
            total_views=data["total_views"],
            regions=regions,
            recommendation=recommendation,
        )
    except (json.JSONDecodeError, KeyError):
        return None


def save_timezone_cache(cache: TimezoneCache) -> None:
    """保存时区缓存"""
    data = {
        "source_file": cache.source_file,
        "source_mtime": cache.source_mtime,
        "source_md5": cache.source_md5,
        "analyzed_at": cache.analyzed_at,
        "total_views": cache.total_views,
        "regions": [
            {
                "code": r.code,
                "views": r.views,
                "weight": r.weight,
                "timezone": r.timezone,
            }
            for r in cache.regions
        ],
        "recommendation": {
            "optimal_time": cache.recommendation.optimal_time,
            "secondary_time": cache.recommendation.secondary_time,
            "user_timezone": cache.recommendation.user_timezone,
            "primary_tz_weight": cache.recommendation.primary_tz_weight,
            "reason": cache.recommendation.reason,
        } if cache.recommendation else None,
    }
    
    with open(TIMEZONE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def analyze_and_cache(
    force: bool = False,
    log_callback=None,
) -> Optional[TimezoneCache]:
    """
    分析地理位置数据并缓存结果
    
    Args:
        force: 是否强制重新分析（忽略缓存）
        log_callback: 日志回调函数
    
    Returns:
        TimezoneCache 或 None
    """
    def log(msg: str):
        if log_callback:
            log_callback(msg)
    
    # 查找 CSV 文件
    csv_file = find_geo_csv_file()
    if not csv_file:
        log("⚠️  未找到地理位置数据文件")
        return None
    
    log(f"📊 找到地理位置数据: {csv_file.name}")
    
    # 检查缓存
    cache = load_timezone_cache()
    current_mtime = csv_file.stat().st_mtime
    current_md5 = calculate_file_md5(csv_file)
    
    if cache and not force:
        # 检查文件是否更新
        if (cache.source_file == str(csv_file) and
            abs(cache.source_mtime - current_mtime) < 1 and
            cache.source_md5 == current_md5):
            log("✅ 使用缓存的时区分析结果")
            return cache
    
    # 重新分析
    log("📈 正在分析地理位置数据...")
    
    regions = parse_geo_csv(csv_file)
    if not regions:
        log("⚠️  未能解析地理位置数据")
        return None
    
    recommendation = calculate_best_upload_time(regions)
    
    total_views = sum(r.views for r in regions)
    
    cache = TimezoneCache(
        source_file=str(csv_file),
        source_mtime=current_mtime,
        source_md5=current_md5,
        analyzed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_views=total_views,
        regions=regions,
        recommendation=recommendation,
    )
    
    save_timezone_cache(cache)
    log("✅ 时区分析完成，已缓存结果")
    
    return cache


def get_time_recommendation() -> Optional[TimeRecommendation]:
    """
    获取时间推荐（优先使用缓存）
    
    Returns:
        TimeRecommendation 或 None
    """
    cache = load_timezone_cache()
    if cache:
        return cache.recommendation
    
    # 没有缓存，尝试分析
    cache = analyze_and_cache()
    return cache.recommendation if cache else None


def format_time_suggestion(
    recommendation: TimeRecommendation,
    current_hour: Optional[int] = None,
) -> str:
    """
    格式化时间建议提示
    
    Args:
        recommendation: 时间推荐
        current_hour: 当前小时（可选，用于判断是否在推荐时段）
    
    Returns:
        格式化的提示字符串
    """
    lines = [
        "",
        "⏰  发布时间建议",
        "━" * 40,
    ]
    
    if current_hour is not None:
        lines.append(f"  当前时间: {current_hour:02d}:00 (北京时间)")
        lines.append("")
        
        # 解析推荐时段
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
    """
    检查当前是否是好的上传时间
    
    Args:
        current_hour: 当前小时（可选，默认使用系统时间）
    
    Returns:
        (is_good, message) 元组
    """
    if current_hour is None:
        current_hour = datetime.now().hour
    
    recommendation = get_time_recommendation()
    if not recommendation:
        return True, "暂无时间推荐数据"
    
    # 解析推荐时段
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
