#!/usr/bin/env python3
"""
小红书视频搬运到 YouTube 的自动化脚本 - CLI 入口

使用方法:
    python -m src.cli -i                    # 交互式模式
    python -m src.cli transfer <小红书视频URL> --title-en "英文标题"
    python -m src.cli fetch <用户主页URL> --output videos.json
    python -m src.cli batch --input video_list.json
    python -m src.cli update --cookie --token
    python -m src.cli status
"""

import argparse
import sys
import json

from src.core import XHSToYouTube
from src.config import TOKEN_FILE


def cmd_transfer(args):
    """执行视频搬运"""
    tags = None
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",")]
    
    translate = args.translate or args.translate_title or args.translate_desc
    
    tool = XHSToYouTube()
    tool.transfer(
        xhs_url=args.url,
        english_title=args.title_en,
        custom_desc=args.desc,
        tags=tags,
        privacy=args.privacy,
        keep_video=args.keep_video,
        translate=translate,
        translate_title=args.translate or args.translate_title,
        translate_desc=args.translate or args.translate_desc
    )


def cmd_fetch(args):
    """获取用户视频列表"""
    tool = XHSToYouTube()
    tool.fetch_user_videos(
        user_url=args.url,
        output_file=args.output,
        page_size=args.page_size
    )


def cmd_batch(args):
    """执行批量搬运"""
    translate = args.translate or args.translate_title or args.translate_desc
    
    tool = XHSToYouTube()
    tool.batch_transfer(
        video_list_path=args.input,
        interval_min=args.interval_min,
        interval_max=args.interval_max,
        privacy=args.privacy,
        keep_video=args.keep_video,
        skip_uploaded=not args.force,
        translate=translate,
        translate_title=args.translate or args.translate_title,
        translate_desc=args.translate or args.translate_desc
    )


def cmd_update(args):
    """更新凭证"""
    tool = XHSToYouTube()
    
    update_all = not (args.cookie or args.token)
    
    if args.cookie or update_all:
        print("\n" + "=" * 50)
        print("[更新] 小红书 Cookie")
        print("=" * 50)
        print("请粘贴 Cookie 内容（JSON 或 Netscape 格式），输入空行结束：")
        
        lines = []
        while True:
            line = input()
            if not line.strip():
                break
            lines.append(line)
        
        content = "\n".join(lines).strip()
        if content:
            tool.update_cookie(content)
            print("[完成] Cookie 已更新")
        else:
            print("[跳过] 未输入内容")
    
    if args.token or update_all:
        print("\n" + "=" * 50)
        print("[更新] YouTube OAuth Token")
        print("=" * 50)
        result = tool.get_authorization_url()
        if result[0]:
            print(f"\n请访问以下链接授权：\n{result[1]}\n")
            code = input("请输入授权码：").strip()
            if code:
                auth_result = tool.authorize_youtube_with_code(code)
                if auth_result[0]:
                    print("[完成] Token 已更新")
                else:
                    print(f"[错误] {auth_result[1]}")
            else:
                print("[跳过] 未输入授权码")


def cmd_status(args):
    """查看凭证状态"""
    tool = XHSToYouTube()
    
    print("\n" + "=" * 50)
    print("凭证状态检查")
    print("=" * 50)
    
    statuses = tool.check_credentials()
    
    for name, status in statuses.items():
        icon = "✓" if status.valid else "✗"
        print(f"\n[{icon}] {status.name}")
        print(f"    路径: {status.path}")
        print(f"    状态: {status.message}")
    
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
            expiry = token_data.get('expiry', '')
            if expiry:
                print(f"\n[Token 过期时间] {expiry}")
        except:
            pass
    
    print("\n" + "=" * 50)


def cmd_analyze(args):
    """分析受众数据，生成完整画像报告"""
    from src.analyze import (
        analyze_and_cache,
        format_audience_report,
    )
    from datetime import datetime
    
    print("\n" + "=" * 50)
    print("受众画像分析")
    print("=" * 50)
    
    # 强制重新分析
    if args.force:
        print("[模式] 强制重新分析")
    
    cache = analyze_and_cache(force=args.force, log_callback=print)
    
    if cache:
        current_hour = datetime.now().hour
        report = format_audience_report(cache, current_hour)
        print(report)
        
        # 显示详细地区分布
        if args.verbose and cache.regions:
            print("\n📊 详细地区分布 (Top 10):")
            for i, region in enumerate(cache.regions[:10]):
                print(f"  {i+1}. {region.code}: {region.views:,} 次 ({region.weight*100:.1f}%) [{region.timezone}]")
        
        # 显示详细年龄分布
        if args.verbose and cache.demographics and cache.demographics.age_gender_breakdown:
            print("\n📊 详细年龄-性别交叉数据:")
            for item in cache.demographics.age_gender_breakdown[:10]:
                print(f"  {item['age_range']} / {item['gender']}: {item['views_percent']:.2f}%")
    else:
        print("\n⚠️  未能生成受众画像")
        print("请确保 data 目录下有包含'表格数据.csv'的数据目录")


def main():
    parser = argparse.ArgumentParser(
        description="小红书视频搬运到 YouTube",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 交互式模式（推荐）
    python -m src.cli -i

    # 搬运单个视频
    python -m src.cli transfer "https://www.xiaohongshu.com/explore/xxx"

    # 搬运视频并添加英文标题
    python -m src.cli transfer "https://www.xiaohongshu.com/explore/xxx" --title-en "My English Title"

    # 获取用户主页所有视频链接
    python -m src.cli fetch "https://www.xiaohongshu.com/user/profile/xxx"

    # 批量上传视频列表
    python -m src.cli batch

    # 分析地理位置数据，获取最佳发布时间
    python -m src.cli analyze

    # 强制重新分析
    python -m src.cli analyze --force --verbose

    # 更新所有凭证
    python -m src.cli update

    # 查看凭证状态
    python -m src.cli status
        """
    )
    
    parser.add_argument("-i", "--interactive", action="store_true",
                       help="启动交互式命令行界面")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # transfer 子命令
    transfer_parser = subparsers.add_parser("transfer", help="搬运视频到 YouTube")
    transfer_parser.add_argument("url", help="小红书视频 URL")
    transfer_parser.add_argument("--title-en", help="英文标题（手动指定）")
    transfer_parser.add_argument("--desc", help="自定义视频描述")
    transfer_parser.add_argument("--tags", help="视频标签，用逗号分隔")
    transfer_parser.add_argument("--privacy", default="public", 
                       choices=["public", "unlisted", "private"],
                       help="隐私设置 (默认: public)")
    transfer_parser.add_argument("--keep-video", action="store_true",
                       help="上传后保留本地视频文件")
    transfer_parser.add_argument("--translate", action="store_true",
                       help="启用自动翻译（标题+描述）")
    transfer_parser.add_argument("--translate-title", action="store_true",
                       help="仅翻译标题")
    transfer_parser.add_argument("--translate-desc", action="store_true",
                       help="仅翻译描述")
    transfer_parser.set_defaults(func=cmd_transfer)
    
    # fetch 子命令
    fetch_parser = subparsers.add_parser("fetch", help="获取用户视频列表")
    fetch_parser.add_argument("url", help="小红书用户主页 URL")
    fetch_parser.add_argument("--output", "-o", help="输出文件路径 (默认: data/video_list.json)")
    fetch_parser.add_argument("--page-size", "-p", type=int, default=10,
                       help="每页获取数量 (默认: 10)")
    fetch_parser.set_defaults(func=cmd_fetch)
    
    # batch 子命令
    batch_parser = subparsers.add_parser("batch", help="批量搬运视频列表")
    batch_parser.add_argument("--input", "-i", help="视频列表文件路径 (默认: data/video_list.json)")
    batch_parser.add_argument("--interval-min", type=int, default=10,
                       help="最小间隔秒数 (默认: 10)")
    batch_parser.add_argument("--interval-max", type=int, default=30,
                       help="最大间隔秒数 (默认: 30)")
    batch_parser.add_argument("--privacy", default="public",
                       choices=["public", "unlisted", "private"],
                       help="隐私设置 (默认: public)")
    batch_parser.add_argument("--keep-video", action="store_true",
                       help="上传后保留本地视频文件")
    batch_parser.add_argument("--force", action="store_true",
                       help="强制重新上传（不跳过已上传视频）")
    batch_parser.add_argument("--translate", action="store_true",
                       help="启用自动翻译（标题+描述）")
    batch_parser.add_argument("--translate-title", action="store_true",
                       help="仅翻译标题")
    batch_parser.add_argument("--translate-desc", action="store_true",
                       help="仅翻译描述")
    batch_parser.set_defaults(func=cmd_batch)
    
    # update 子命令
    update_parser = subparsers.add_parser("update", help="更新凭证（Cookie/Token）")
    update_parser.add_argument("--cookie", "-c", action="store_true",
                       help="只更新小红书 Cookie")
    update_parser.add_argument("--token", "-t", action="store_true",
                       help="只更新 YouTube Token")
    update_parser.set_defaults(func=cmd_update)
    
    # status 子命令
    status_parser = subparsers.add_parser("status", help="查看凭证状态")
    status_parser.set_defaults(func=cmd_status)
    
    # analyze 子命令
    analyze_parser = subparsers.add_parser("analyze", help="分析地理位置数据，推荐最佳发布时间")
    analyze_parser.add_argument("--force", "-f", action="store_true",
                       help="强制重新分析（忽略缓存）")
    analyze_parser.add_argument("--verbose", "-v", action="store_true",
                       help="显示详细地区分布")
    analyze_parser.set_defaults(func=cmd_analyze)
    
    args = parser.parse_args()
    
    # 交互式模式
    if args.interactive:
        from src.interactive import main as interactive_main
        interactive_main()
        return
    
    # 如果没有指定子命令，显示帮助
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行对应的命令
    args.func(args)


if __name__ == "__main__":
    main()
