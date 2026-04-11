#!/usr/bin/env python3
"""
小红书视频搬运到 YouTube 的自动化脚本 - CLI 入口

使用方法:
    python -m src.cli -i                    # 交互式模式
    python -m src.cli transfer <小红书视频URL> --title-en "英文标题"
    python -m src.cli fetch <用户主页URL> --output videos.json
    python -m src.cli batch --input video_list.json
    python -m src.cli schedule --time 08:00 --limit 3
    python -m src.cli schedule --list
    python -m src.cli schedule --status
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
        translate_desc=args.translate or args.translate_desc,
        show_time_suggestion=args.time_confirm,
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
    # 默认开启翻译，除非指定 --no-translate
    translate = not args.no_translate or args.translate_title or args.translate_desc
    from src.notification import notify_upload_result
    from pathlib import Path

    tool = XHSToYouTube()
    result = tool.batch_transfer(
        video_list_path=args.input,
        interval_min=args.interval_min,
        interval_max=args.interval_max,
        privacy=args.privacy,
        keep_video=args.keep_video,
        skip_uploaded=not args.force,
        translate=translate,
        translate_title=translate or args.translate_title,
        translate_desc=translate or args.translate_desc,
        limit=args.limit,
        show_time_suggestion=args.time_confirm,
    )

    task_name = f"batch:{Path(args.input).name}" if args.input else "batch"
    if result.get("success") or result.get("failed_videos"):
        notify_upload_result(task_name, result)
    else:
        notify_upload_result(task_name, result, result.get("message"))


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
        except (OSError, json.JSONDecodeError) as e:
            print(f"\n[警告] 无法读取 Token 过期时间: {e}")
    
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


def cmd_notify(args):
    """测试通知通道连通性"""
    from src.notification import test_notification_delivery

    print("\n" + "=" * 50)
    print("通知通信测试")
    print("=" * 50)

    result = test_notification_delivery(message=args.message, channel=args.channel)

    print(f"\n通知功能: {'启用' if result['enabled'] else '未启用'}")
    print(f"测试通道: {result['channel']}")

    for channel_name in ("telegram", "feishu"):
        channel_result = result[channel_name]
        print(f"\n[{channel_name.capitalize()}]")
        print(f"  已配置: {'是' if channel_result['configured'] else '否'}")
        print(f"  结果: {channel_result['message'] or '未测试'}")

    print(f"\n总体结果: {'成功' if result['success'] else '失败'}")
    if result.get("message"):
        print(f"说明: {result['message']}")

    print("\n" + "=" * 50)


def cmd_schedule(args):
    """执行定时上传任务"""
    from src.schedule import (
        run_scheduled_upload,
        list_schedule_tasks,
        generate_crontab_entries,
        get_today_schedule_status,
    )
    from src.notification import notify_upload_result
    from src.config import ensure_logs_dir
    
    # 确保日志目录存在
    ensure_logs_dir()
    
    # 列出任务配置
    if args.list:
        print("\n" + "=" * 50)
        print("定时任务配置")
        print("=" * 50)
        
        tasks = list_schedule_tasks()
        for i, task in enumerate(tasks, 1):
            status = "✓ 启用" if task.get("enabled", True) else "✗ 禁用"
            print(f"\n{i}. [{status}] {task.get('time', 'N/A')}")
            print(f"   描述: {task.get('description', 'N/A')}")
            print(f"   数量: {task.get('limit', 3)} 个视频")
        
        print("\n" + "=" * 50)
        return
    
    # 显示今日状态
    if args.status:
        print("\n" + "=" * 50)
        print("今日调度状态")
        print("=" * 50)
        
        status = get_today_schedule_status()
        print(f"\n日期: {status['date']}")
        print(f"当前时间: {status['current_time']}")
        print(f"今日已上传: {status['today_uploads']} 个")
        
        print("\n任务状态:")
        for task in status["tasks"]:
            status_icon = {
                "completed": "✅",
                "running": "🔄",
                "pending": "⏳",
            }.get(task["status"], "❓")
            print(f"  {status_icon} {task['time']} - {task['description']} (计划: {task['limit']})")
        
        print("\n" + "=" * 50)
        return
    
    # 生成 crontab 配置
    if args.install_cron:
        print("\n" + "=" * 50)
        print("Crontab 配置")
        print("=" * 50)
        print("\n请将以下内容添加到 crontab (crontab -e):\n")
        print(generate_crontab_entries(python_path=args.python_path))
        print("=" * 50)
        return
    
    # 执行定时上传
    print("\n" + "=" * 50)
    print("定时上传任务")
    print("=" * 50)
    
    result = run_scheduled_upload(
        time_str=args.time,
        limit=args.limit,
        log_callback=print,
    )
    
    # 发送通知
    if result.get("success") or result.get("failed_videos"):
        notify_upload_result(args.time or "auto", result)
    else:
        notify_upload_result(args.time or "auto", result, result.get("message"))
    
    print("\n" + "=" * 50)


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

    # 批量上传，限制上传数量
    python -m src.cli batch --limit 5

    # 分析地理位置数据，获取最佳发布时间
    python -m src.cli analyze

    # 强制重新分析
    python -m src.cli analyze --force --verbose

    # 测试通知连通性
    python -m src.cli notify --channel telegram

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
    transfer_parser.add_argument("--time-confirm", action="store_true",
                       help="启用推荐发布时间提示，并在非推荐时段上传前确认")
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
    batch_parser.add_argument("--no-translate", action="store_true",
                       help="禁用自动翻译（默认开启翻译）")
    batch_parser.add_argument("--translate-title", action="store_true",
                       help="仅翻译标题")
    batch_parser.add_argument("--translate-desc", action="store_true",
                       help="仅翻译描述")
    batch_parser.add_argument("--limit", "-l", type=int, default=0,
                       help="上传数量限制 (默认: 0=不限制)")
    batch_parser.add_argument("--time-confirm", action="store_true",
                       help="批量上传时启用推荐发布时间提示，并在非推荐时段逐个确认")
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

    # notify 子命令
    notify_parser = subparsers.add_parser("notify", help="测试 Telegram / 飞书通知连通性")
    notify_parser.add_argument(
        "--channel",
        choices=["all", "telegram", "feishu"],
        default="all",
        help="测试指定通道 (默认: all)",
    )
    notify_parser.add_argument(
        "--message",
        default="通知通信测试",
        help="测试消息内容",
    )
    notify_parser.set_defaults(func=cmd_notify)
    
    # analyze 子命令
    analyze_parser = subparsers.add_parser("analyze", help="分析地理位置数据，推荐最佳发布时间")
    analyze_parser.add_argument("--force", "-f", action="store_true",
                       help="强制重新分析（忽略缓存）")
    analyze_parser.add_argument("--verbose", "-v", action="store_true",
                       help="显示详细地区分布")
    analyze_parser.set_defaults(func=cmd_analyze)
    
    # schedule 子命令
    schedule_parser = subparsers.add_parser("schedule", help="执行定时上传任务")
    schedule_parser.add_argument("--time", "-t",
                       help="任务时间 (格式: HH:MM，如 08:00)")
    schedule_parser.add_argument("--limit", "-l", type=int,
                       help="上传数量限制 (默认从配置读取)")
    schedule_parser.add_argument("--list", action="store_true",
                       help="列出所有定时任务配置")
    schedule_parser.add_argument("--status", action="store_true",
                       help="显示今日调度状态")
    schedule_parser.add_argument("--install-cron", action="store_true",
                       help="生成 crontab 配置")
    schedule_parser.add_argument("--python-path",
                       help="指定 Python 解释器路径 (用于 crontab)")
    schedule_parser.set_defaults(func=cmd_schedule)
    
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
