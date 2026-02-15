#!/usr/bin/env python3
"""
小红书视频搬运到 YouTube 的自动化脚本

使用方法:
    python main.py <小红书视频URL> --title-en "英文标题"
    python main.py <小红书视频URL> --title-en "English Title" --desc "视频描述"
"""

import argparse
import sys

from core import XHSToYouTube


def main():
    parser = argparse.ArgumentParser(
        description="小红书视频搬运到 YouTube",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 基本用法（使用原标题）
    python main.py "https://www.xiaohongshu.com/explore/xxx"

    # 添加英文标题（双语标题）
    python main.py "https://www.xiaohongshu.com/explore/xxx" --title-en "My English Title"

    # 自定义标签和隐私设置
    python main.py "https://www.xiaohongshu.com/explore/xxx" --tags "vlog,life,daily" --privacy unlisted

    # 保留本地视频文件
    python main.py "https://www.xiaohongshu.com/explore/xxx" --keep-video
        """
    )
    
    parser.add_argument("url", help="小红书视频 URL")
    parser.add_argument("--title-en", help="英文标题（生成双语标题）")
    parser.add_argument("--desc", help="自定义视频描述")
    parser.add_argument("--tags", help="视频标签，用逗号分隔")
    parser.add_argument("--privacy", default="public", 
                       choices=["public", "unlisted", "private"],
                       help="隐私设置 (默认: public)")
    parser.add_argument("--keep-video", action="store_true",
                       help="上传后保留本地视频文件")
    
    args = parser.parse_args()
    
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


if __name__ == "__main__":
    main()