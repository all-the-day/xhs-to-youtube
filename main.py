#!/usr/bin/env python3
"""
小红书视频搬运到 YouTube 的自动化脚本

使用方法:
    python main.py transfer <小红书视频URL> --title-en "英文标题"
    python main.py fetch <用户主页URL> --output videos.json
    python main.py batch --input video_list.json
"""

import argparse
import sys

from core import XHSToYouTube


def cmd_transfer(args):
    """执行视频搬运"""
    # 处理标签
    tags = None
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",")]
    
    # 执行搬运
    tool = XHSToYouTube()
    tool.transfer(
        xhs_url=args.url,
        english_title=args.title_en,
        custom_desc=args.desc,
        tags=tags,
        privacy=args.privacy,
        keep_video=args.keep_video
    )


def cmd_fetch(args):
    """获取用户视频列表"""
    tool = XHSToYouTube()
    tool.fetch_user_videos(
        user_url=args.url,
        output_file=args.output
    )


def cmd_batch(args):
    """执行批量搬运"""
    tool = XHSToYouTube()
    tool.batch_transfer(
        video_list_path=args.input,
        interval_min=args.interval_min,
        interval_max=args.interval_max,
        privacy=args.privacy,
        keep_video=args.keep_video,
        skip_uploaded=not args.force
    )


def main():
    parser = argparse.ArgumentParser(
        description="小红书视频搬运到 YouTube",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 搬运单个视频
    python main.py transfer "https://www.xiaohongshu.com/explore/xxx"

    # 搬运视频并添加英文标题
    python main.py transfer "https://www.xiaohongshu.com/explore/xxx" --title-en "My English Title"

    # 获取用户主页所有视频链接
    python main.py fetch "https://www.xiaohongshu.com/user/profile/xxx"

    # 获取用户视频并保存到指定文件
    python main.py fetch "https://www.xiaohongshu.com/user/profile/xxx" --output my_videos.json

    # 批量上传视频列表（使用默认 video_list.json）
    python main.py batch

    # 批量上传指定文件，自定义间隔时间
    python main.py batch --input my_videos.json --interval-min 15 --interval-max 45

    # 强制重新上传所有视频（不跳过已上传）
    python main.py batch --force
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # transfer 子命令
    transfer_parser = subparsers.add_parser("transfer", help="搬运视频到 YouTube")
    transfer_parser.add_argument("url", help="小红书视频 URL")
    transfer_parser.add_argument("--title-en", help="英文标题（生成双语标题）")
    transfer_parser.add_argument("--desc", help="自定义视频描述")
    transfer_parser.add_argument("--tags", help="视频标签，用逗号分隔")
    transfer_parser.add_argument("--privacy", default="public", 
                       choices=["public", "unlisted", "private"],
                       help="隐私设置 (默认: public)")
    transfer_parser.add_argument("--keep-video", action="store_true",
                       help="上传后保留本地视频文件")
    transfer_parser.set_defaults(func=cmd_transfer)
    
    # fetch 子命令
    fetch_parser = subparsers.add_parser("fetch", help="获取用户视频列表")
    fetch_parser.add_argument("url", help="小红书用户主页 URL")
    fetch_parser.add_argument("--output", "-o", help="输出文件路径 (默认: user_videos_{user_id}.json)")
    fetch_parser.set_defaults(func=cmd_fetch)
    
    # batch 子命令
    batch_parser = subparsers.add_parser("batch", help="批量搬运视频列表")
    batch_parser.add_argument("--input", "-i", help="视频列表文件路径 (默认: video_list.json)")
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
    batch_parser.set_defaults(func=cmd_batch)
    
    args = parser.parse_args()
    
    # 如果没有指定子命令，显示帮助
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行对应的命令
    args.func(args)


if __name__ == "__main__":
    main()
