#!/usr/bin/env python3
"""
小红书视频搬运到 YouTube 的自动化脚本

使用方法:
    python main.py transfer <小红书视频URL> --title-en "英文标题"
    python main.py fetch <用户主页URL> --output videos.json
    python main.py batch --input video_list.json
    python main.py update --cookie --token
    python main.py status
"""

import argparse
import sys
import json
from pathlib import Path

from core import XHSToYouTube, COOKIES_FILE, TOKEN_FILE, CREDENTIALS_FILE


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
        output_file=args.output,
        page_size=args.page_size
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


def cmd_update(args):
    """更新凭证"""
    tool = XHSToYouTube()
    
    # 如果没有指定任何选项，更新所有
    update_all = not (args.cookie or args.token)
    
    # 更新 Cookie
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
    
    # 更新 Token
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
    
    # 额外检查 Token 过期时间
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

    # 获取用户主页所有视频链接（默认每页10条）
    python main.py fetch "https://www.xiaohongshu.com/user/profile/xxx"

    # 获取用户视频，每页20条
    python main.py fetch "https://www.xiaohongshu.com/user/profile/xxx" --page-size 20

    # 获取用户视频并保存到指定文件
    python main.py fetch "https://www.xiaohongshu.com/user/profile/xxx" --output my_videos.json

    # 批量上传视频列表（使用默认 video_list.json）
    python main.py batch

    # 批量上传指定文件，自定义间隔时间
    python main.py batch --input my_videos.json --interval-min 15 --interval-max 45

    # 强制重新上传所有视频（不跳过已上传）
    python main.py batch --force

    # 更新所有凭证
    python main.py update

    # 只更新 Cookie
    python main.py update --cookie

    # 只更新 Token
    python main.py update --token

    # 查看凭证状态
    python main.py status
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
    fetch_parser.add_argument("--output", "-o", help="输出文件路径 (默认: video_list.json)")
    fetch_parser.add_argument("--page-size", "-p", type=int, default=10,
                       help="每页获取数量 (默认: 10)")
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
    
    args = parser.parse_args()
    
    # 如果没有指定子命令，显示帮助
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 执行对应的命令
    args.func(args)


if __name__ == "__main__":
    main()
