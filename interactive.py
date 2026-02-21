#!/usr/bin/env python3
"""
小红书视频搬运工具 - 交互式命令行界面
"""

import sys
import os
import json
from pathlib import Path

from core import XHSToYouTube, COOKIES_FILE, TOKEN_FILE, CREDENTIALS_FILE


def clear_screen():
    """清屏"""
    os.system('clear' if os.name == 'posix' else 'cls')


def print_header():
    """打印标题"""
    print("\n" + "=" * 50)
    print("  小红书 → YouTube 视频搬运工具")
    print("=" * 50)


def print_credential_status(tool: XHSToYouTube):
    """打印凭证状态摘要"""
    statuses = tool.check_credentials()
    
    cookie_status = "✓" if statuses.get('cookie', {}).valid else "✗"
    token_status = "✓" if statuses.get('token', {}).valid else "✗"
    
    print(f"\n[凭证状态] Cookie: {cookie_status} | Token: {token_status}")


def input_with_default(prompt: str, default: str = None) -> str:
    """带默认值的输入"""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    else:
        return input(f"{prompt}: ").strip()


def confirm(message: str) -> bool:
    """确认操作"""
    while True:
        result = input(f"{message} (y/n): ").strip().lower()
        if result in ('y', 'yes', '是'):
            return True
        elif result in ('n', 'no', '否'):
            return False
        print("请输入 y 或 n")


def select_option(options: list, prompt: str = "请选择") -> int:
    """
    选择选项
    
    Args:
        options: 选项列表
        prompt: 提示信息
    
    Returns:
        选择的索引（从 0 开始）
    """
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    
    while True:
        try:
            choice = input(f"\n{prompt} [1-{len(options)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
            print(f"请输入 1 到 {len(options)} 之间的数字")
        except ValueError:
            print("请输入有效数字")


def menu_single_transfer(tool: XHSToYouTube):
    """单个视频搬运"""
    print("\n" + "-" * 50)
    print("单个视频搬运")
    print("-" * 50)
    
    # 输入视频 URL
    url = input("请输入小红书视频 URL: ").strip()
    if not url:
        print("[取消] 未输入 URL")
        input("\n按回车键继续...")
        return
    
    # 英文标题（可选）
    title_en = input("英文标题（可选，留空跳过）: ").strip() or None
    
    # 自定义描述（可选）
    custom_desc = input("自定义描述（可选，留空跳过）: ").strip() or None
    
    # 标签（可选）
    tags_input = input("标签（可选，逗号分隔，留空跳过）: ").strip()
    tags = [t.strip() for t in tags_input.split(",")] if tags_input else None
    
    # 隐私设置
    print("\n隐私设置:")
    privacy_options = ["公开", "不公开", "私享"]
    privacy_idx = select_option(privacy_options, "请选择隐私设置")
    privacy = ["public", "unlisted", "private"][privacy_idx]
    
    # 是否保留视频
    keep_video = confirm("上传后是否保留本地视频文件?")
    
    # 确认执行
    print("\n" + "-" * 30)
    print("即将执行搬运:")
    print(f"  URL: {url}")
    if title_en:
        print(f"  英文标题: {title_en}")
    print(f"  隐私设置: {privacy}")
    print(f"  保留本地: {'是' if keep_video else '否'}")
    print("-" * 30)
    
    if not confirm("确认执行?"):
        print("[取消] 用户取消操作")
        input("\n按回车键继续...")
        return
    
    # 执行搬运
    print()
    try:
        tool.transfer(
            xhs_url=url,
            english_title=title_en,
            custom_desc=custom_desc,
            tags=tags,
            privacy=privacy,
            keep_video=keep_video
        )
    except Exception as e:
        print(f"\n[错误] {e}")
    
    input("\n按回车键继续...")


def menu_fetch_videos(tool: XHSToYouTube):
    """获取用户视频列表"""
    print("\n" + "-" * 50)
    print("获取用户视频列表")
    print("-" * 50)
    
    # 输入用户 URL
    url = input("请输入小红书用户主页 URL: ").strip()
    if not url:
        print("[取消] 未输入 URL")
        input("\n按回车键继续...")
        return
    
    # 每页数量
    page_size = input_with_default("每页获取数量", "10")
    try:
        page_size = int(page_size)
    except ValueError:
        page_size = 10
    
    # 输出文件
    output_file = input_with_default("输出文件路径", "video_list.json")
    
    # 执行获取
    print("\n" + "-" * 30)
    print("开始获取视频列表...")
    print("-" * 30)
    
    try:
        result = tool.fetch_user_videos(
            user_url=url,
            output_file=output_file,
            page_size=page_size
        )
        print(f"\n[完成] 获取到 {result.get('total_count', 0)} 个视频")
        print(f"[保存] 已保存到: {output_file}")
    except Exception as e:
        print(f"\n[错误] {e}")
    
    input("\n按回车键继续...")


def menu_batch_transfer(tool: XHSToYouTube):
    """批量搬运上传"""
    print("\n" + "-" * 50)
    print("批量搬运上传")
    print("-" * 50)
    
    # 选择视频列表文件
    default_file = "video_list.json"
    input_file = input_with_default("视频列表文件路径", default_file)
    
    # 检查文件是否存在
    if not Path(input_file).exists():
        print(f"[错误] 文件不存在: {input_file}")
        input("\n按回车键继续...")
        return
    
    # 显示文件内容预览
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        videos = data.get('videos', [])
        total = len(videos)
        print(f"\n[预览] 共 {total} 个视频")
        if videos:
            print("前 3 个视频:")
            for i, v in enumerate(videos[:3], 1):
                print(f"  {i}. {v.get('title', '未知标题')[:40]}")
            if total > 3:
                print(f"  ... 还有 {total - 3} 个视频")
    except Exception as e:
        print(f"[错误] 读取文件失败: {e}")
        input("\n按回车键继续...")
        return
    
    # 上传间隔
    print("\n上传间隔设置:")
    interval_min = input_with_default("最小间隔（秒）", "10")
    interval_max = input_with_default("最大间隔（秒）", "30")
    try:
        interval_min = int(interval_min)
        interval_max = int(interval_max)
    except ValueError:
        interval_min, interval_max = 10, 30
    
    # 隐私设置
    print("\n隐私设置:")
    privacy_options = ["公开", "不公开", "私享"]
    privacy_idx = select_option(privacy_options, "请选择隐私设置")
    privacy = ["public", "unlisted", "private"][privacy_idx]
    
    # 是否保留视频
    keep_video = confirm("上传后是否保留本地视频文件?")
    
    # 是否跳过已上传
    skip_uploaded = confirm("是否跳过已上传的视频?")
    
    # 确认执行
    print("\n" + "-" * 30)
    print("即将执行批量搬运:")
    print(f"  视频数量: {total}")
    print(f"  上传间隔: {interval_min}-{interval_max} 秒")
    print(f"  隐私设置: {privacy}")
    print(f"  保留本地: {'是' if keep_video else '否'}")
    print(f"  跳过已上传: {'是' if skip_uploaded else '否'}")
    print("-" * 30)
    
    if not confirm("确认执行?"):
        print("[取消] 用户取消操作")
        input("\n按回车键继续...")
        return
    
    # 执行批量搬运
    print()
    try:
        tool.batch_transfer(
            video_list_path=input_file,
            interval_min=interval_min,
            interval_max=interval_max,
            privacy=privacy,
            keep_video=keep_video,
            skip_uploaded=skip_uploaded
        )
    except Exception as e:
        print(f"\n[错误] {e}")
    
    input("\n按回车键继续...")


def menu_update_credentials(tool: XHSToYouTube):
    """更新凭证"""
    print("\n" + "-" * 50)
    print("更新凭证")
    print("-" * 50)
    
    options = ["更新小红书 Cookie", "更新 YouTube Token", "更新全部"]
    choice = select_option(options, "请选择要更新的凭证")
    
    if choice == 0 or choice == 2:
        # 更新 Cookie
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
    
    if choice == 1 or choice == 2:
        # 更新 Token
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
    
    input("\n按回车键继续...")


def menu_check_status(tool: XHSToYouTube):
    """查看凭证状态"""
    print("\n" + "-" * 50)
    print("凭证状态检查")
    print("-" * 50)
    
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
    
    print("\n" + "-" * 50)
    input("\n按回车键继续...")


def main():
    """主函数"""
    tool = XHSToYouTube()
    
    while True:
        clear_screen()
        print_header()
        print_credential_status(tool)
        
        print("\n请选择操作:")
        print("  1. 单个视频搬运")
        print("  2. 获取用户视频列表")
        print("  3. 批量搬运上传")
        print("  4. 更新凭证")
        print("  5. 查看凭证状态")
        print("  0. 退出")
        
        choice = input("\n请输入选项 [0-5]: ").strip()
        
        if choice == '1':
            menu_single_transfer(tool)
        elif choice == '2':
            menu_fetch_videos(tool)
        elif choice == '3':
            menu_batch_transfer(tool)
        elif choice == '4':
            menu_update_credentials(tool)
        elif choice == '5':
            menu_check_status(tool)
        elif choice == '0':
            print("\n再见！")
            break
        else:
            print("无效选项，请重新选择")
            input("\n按回车键继续...")


if __name__ == "__main__":
    main()
