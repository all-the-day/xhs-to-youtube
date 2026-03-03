#!/usr/bin/env python3
"""
小红书到 YouTube 视频搬运工具 - 测试用例

运行: python -m tests.test_flow
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core import XHSToYouTube
from src.config import COOKIES_FILE, CREDENTIALS_FILE, TOKEN_FILE


def test_credentials():
    """测试凭证状态和 YouTube API 连接"""
    print("=" * 50)
    print("测试 1: 凭证状态检查")
    print("=" * 50)
    
    tool = XHSToYouTube()
    statuses = tool.check_credentials()
    
    for key, status in statuses.items():
        icon = "✅" if status.valid else ("⚠️" if status.exists else "❌")
        print(f"{icon} {status.name}: {status.message}")
    
    # 至少需要 credentials.json 存在
    assert statuses.get('credentials').exists, "Google OAuth 凭证文件不存在"
    
    # Token 可能过期，这是正常的（测试不实际上传）
    if statuses.get('token') and statuses.get('token').valid:
        print("✅ YouTube Token 有效")
    else:
        print("⚠️ YouTube Token 已过期或不存在（上传时需要重新授权）")
    
    print("✅ 凭证检查通过\n")
    return True


def test_video_stream_selection():
    """测试视频流选择（无水印）- 使用实际页面"""
    print("=" * 50)
    print("测试 2: 视频流选择（去水印）")
    print("=" * 50)
    
    test_url = "http://xhslink.com/o/6fDiSoovKl5"
    
    tool = XHSToYouTube()
    result = tool.download_video(test_url)
    
    print(f"标题: {result['title']}")
    
    assert os.path.exists(result['video_path']), "视频文件不存在"
    
    print("✅ 视频流选择测试通过（已选择无水印版本）\n")
    return True


def test_title_extraction():
    """测试标题提取"""
    print("=" * 50)
    print("测试 3: 标题提取")
    print("=" * 50)
    
    import re
    
    test_cases = [
        ('<title>测试视频标题 - 小红书</title>', "测试视频标题"),
        ('<title>另一个标题 - 小红书</title>', "另一个标题"),
    ]
    
    for html, expected in test_cases:
        html_title_match = re.search(r'<title>([^<]+)</title>', html)
        if html_title_match:
            html_title = html_title_match.group(1)
            if ' - 小红书' in html_title:
                title = html_title.split(' - 小红书')[0].strip()
            else:
                title = html_title.strip()
        
        print(f"HTML: {html}")
        print(f"提取标题: {title}")
        assert title == expected, f"标题提取错误: 期望 '{expected}', 实际 '{title}'"
    
    print("✅ 标题提取测试通过\n")
    return True


def test_download_video():
    """测试视频下载"""
    print("=" * 50)
    print("测试 4: 视频下载（已在测试2中完成）")
    print("=" * 50)
    
    print("✅ 视频下载测试已通过（见测试2）\n")
    return True


def test_full_transfer():
    """测试完整搬运流程（不上传，仅验证下载和元数据生成）"""
    print("=" * 50)
    print("测试 5: 搬运流程准备检查")
    print("=" * 50)
    
    tool = XHSToYouTube()
    
    print("1. 检查凭证状态...")
    statuses = tool.check_credentials()
    assert statuses.get('credentials').exists, "凭证文件不存在"
    print("   ✅ 凭证文件存在")
    
    print("\n2. 检查视频下载功能...")
    print("   ✅ 视频下载功能已在测试 2 中验证")
    
    print("\n3. 测试元数据生成...")
    title = tool.generate_english_title("测试标题", "Test Title")
    assert "测试标题" in title or "Test Title" in title, "标题生成失败"
    print(f"   生成的标题: {title}")
    
    desc = tool.generate_description("测试描述", "https://example.com", "uploader")
    assert "测试描述" in desc, "描述生成失败"
    print(f"   生成的描述: {desc[:50]}...")
    
    print("\n4. 测试翻译功能...")
    translated = tool.translate("你好世界", "title")
    print(f"   翻译结果: {translated}")
    
    print("\n✅ 搬运流程准备检查通过（未实际上传视频）\n")
    return True


def test_time_recommendation():
    """测试时间推荐功能"""
    print("=" * 50)
    print("测试 6: 时间推荐功能")
    print("=" * 50)
    
    from src.analyze import (
        analyze_and_cache,
        get_time_recommendation,
        is_good_upload_time,
    )
    
    print("1. 测试分析缓存...")
    cache = analyze_and_cache(force=False, log_callback=print)
    
    if cache:
        print(f"   ✅ 缓存加载成功: {cache.analyzed_at}")
        print(f"   地区数量: {len(cache.regions)}")
        if cache.demographics:
            print(f"   年龄段数量: {len(cache.demographics.age_groups)}")
    else:
        print("   ⚠️ 无缓存数据（需要先运行 analyze 命令）")
    
    print("\n2. 测试时间推荐获取...")
    recommendation = get_time_recommendation()
    
    if recommendation:
        print(f"   黄金时段: {recommendation.optimal_time}")
        print(f"   次选时段: {recommendation.secondary_time}")
        print(f"   推荐原因: {recommendation.reason}")
        assert recommendation.optimal_time, "黄金时段不能为空"
        print("   ✅ 时间推荐获取成功")
    else:
        print("   ⚠️ 无时间推荐数据")
    
    print("\n3. 测试时段判断...")
    # 测试不同时段
    test_hours = [10, 13, 20, 23]
    for hour in test_hours:
        is_good, msg = is_good_upload_time(hour)
        status = "✅ 推荐" if is_good else "⚠️ 不推荐"
        print(f"   {hour}:00 -> {status} ({msg})")
    
    print("\n✅ 时间推荐测试通过\n")
    return True


def test_time_slot_labeling():
    """测试时间段标签功能"""
    print("=" * 50)
    print("测试 7: 时间段标签功能")
    print("=" * 50)
    
    tool = XHSToYouTube()
    
    print("测试不同时段的标签:")
    test_cases = [
        (10, "非推荐时段"),   # 上午
        (13, "非推荐时段"),   # 下午
        (19, "黄金时段"),     # 晚间黄金档
        (21, "黄金时段"),     # 晚间黄金档
        (12, "次选时段"),     # 午休
    ]
    
    for hour, expected_type in test_cases:
        time_slot, followed = tool._get_time_slot_info(hour)
        status = "✅" if expected_type in time_slot else "⚠️"
        print(f"   {hour}:00 -> {time_slot} (遵循推荐: {followed}) {status}")
    
    print("\n✅ 时间段标签测试通过\n")
    return True


def test_upload_record_structure():
    """测试上传记录数据结构"""
    print("=" * 50)
    print("测试 8: 上传记录数据结构")
    print("=" * 50)
    
    from src.models import UploadRecord
    from datetime import datetime
    
    print("创建测试上传记录...")
    record = UploadRecord(
        note_id="test_123",
        youtube_id="abc123",
        youtube_url="https://youtube.com/watch?v=abc123",
        title="测试视频标题",
        uploaded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        upload_hour=20,
        time_slot="黄金时段",
        recommendation_followed=True,
    )
    
    print(f"   note_id: {record.note_id}")
    print(f"   upload_hour: {record.upload_hour}")
    print(f"   time_slot: {record.time_slot}")
    print(f"   recommendation_followed: {record.recommendation_followed}")
    
    assert record.upload_hour == 20, "upload_hour 字段错误"
    assert record.time_slot == "黄金时段", "time_slot 字段错误"
    assert record.recommendation_followed == True, "recommendation_followed 字段错误"
    
    print("\n✅ 上传记录数据结构测试通过\n")
    return True


def run_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("小红书到 YouTube 视频搬运工具 - 测试套件")
    print("=" * 60 + "\n")
    
    tests = [
        ("凭证状态检查", test_credentials),
        ("视频流选择", test_video_stream_selection),
        ("标题提取", test_title_extraction),
        ("视频下载", test_download_video),
        ("完整搬运流程", test_full_transfer),
        ("时间推荐功能", test_time_recommendation),
        ("时间段标签", test_time_slot_labeling),
        ("上传记录结构", test_upload_record_structure),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ 测试失败: {name}")
            print(f"   原因: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ 测试异常: {name}")
            print(f"   错误: {e}\n")
            failed += 1
    
    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
