"""
小红书到 YouTube 视频搬运核心类
整合下载、上传、翻译、批量处理等功能
"""

import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List

from src.config import (
    COOKIES_FILE,
    UPLOADED_FILE,
    DAILY_UPLOAD_LIMIT,
)
from src.models import CredentialStatus, UploadRecord
from src.translate import TranslateService
from src.download import VideoDownloader
from src.upload import YouTubeUploader
from src.fetch import VideoFetcher


class XHSToYouTube:
    """
    小红书到 YouTube 视频搬运核心类
    支持进度回调和日志回调
    """

    def __init__(
        self,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ):
        self.log_callback = log_callback
        self.progress_callback = progress_callback

        # 初始化子模块
        self.translate_service = TranslateService(log_callback)
        self.downloader = VideoDownloader(log_callback, progress_callback)
        self.uploader = YouTubeUploader(log_callback, progress_callback)
        self.fetcher = VideoFetcher(log_callback, progress_callback)

    def _log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        print(message)

    def _progress(self, value: float, status: str = ""):
        if self.progress_callback:
            self.progress_callback(value, status)

    # ==================== Cookie 管理 ====================

    def update_cookie(self, content: str) -> bool:
        """更新小红书 Cookie（支持 JSON 和 Netscape 格式）"""
        content = content.strip()

        if content.startswith('['):
            try:
                cookies_json = json.loads(content)
                lines = ["# Netscape HTTP Cookie File", "# This file is generated for xhs-to-youtube", ""]

                for cookie in cookies_json:
                    domain = cookie.get('domain', '').lstrip('.')
                    path = cookie.get('path', '/')
                    secure = cookie.get('secure', False)
                    expiry = cookie.get('expirationDate', 0)
                    name = cookie.get('name', '')
                    value = cookie.get('value', '')

                    if int(expiry) == 0:
                        expiry_str = "0"
                    else:
                        expiry_str = str(int(expiry))

                    line = f"{domain}\tTRUE\t{path}\t{str(secure).upper()}\t{expiry_str}\t{name}\t{value}"
                    lines.append(line)

                with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines) + '\n')

                return True
            except json.JSONDecodeError as e:
                self._log(f"[错误] JSON 解析失败: {e}")
                return False
        else:
            with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
                f.write(content + '\n')
            return True

    # ==================== 凭证检查 ====================

    def check_credentials(self) -> Dict[str, CredentialStatus]:
        """检查所有凭证状态"""
        statuses = {}

        # 检查 Cookie 文件
        if COOKIES_FILE.exists():
            content = COOKIES_FILE.read_text().strip()
            lines = content.split('\n')
            has_valid_cookie = any(
                line.strip() and not line.startswith('#')
                for line in lines
            )
            if has_valid_cookie:
                statuses['cookie'] = CredentialStatus(
                    name="小红书 Cookie",
                    exists=True,
                    valid=True,
                    message="已配置",
                    path=str(COOKIES_FILE)
                )
            else:
                statuses['cookie'] = CredentialStatus(
                    name="小红书 Cookie",
                    exists=True,
                    valid=False,
                    message="文件为空或只有注释",
                    path=str(COOKIES_FILE)
                )
        else:
            statuses['cookie'] = CredentialStatus(
                name="小红书 Cookie",
                exists=False,
                valid=False,
                message="文件不存在",
                path=str(COOKIES_FILE)
            )

        # 检查 Google 凭证
        yt_statuses = self.uploader.check_credentials()
        statuses.update(yt_statuses)

        return statuses

    # ==================== 翻译 ====================

    def translate(self, text: str, target_type: str = "title") -> str:
        """翻译文本"""
        return self.translate_service.translate(text, target_type)

    # ==================== 授权 ====================

    def get_authorization_url(self) -> tuple:
        """获取 YouTube OAuth 授权 URL"""
        return self.uploader.get_authorization_url()

    def authorize_youtube_with_code(self, code: str) -> tuple:
        """使用授权码完成授权"""
        return self.uploader.authorize_youtube_with_code(code)

    def authorize_youtube(self) -> tuple:
        """手动进行 YouTube OAuth 授权"""
        return self.uploader.authorize_youtube()

    # ==================== 下载 ====================

    def download_video(self, url: str, title: str = None, description: str = None) -> dict:
        """下载小红书视频"""
        return self.downloader.download_video(url, title, description)

    # ==================== 上传 ====================

    def upload_to_youtube(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list = None,
        category_id: str = "22",
        privacy_status: str = "public"
    ) -> dict:
        """上传视频到 YouTube"""
        return self.uploader.upload_to_youtube(
            video_path, title, description, tags, category_id, privacy_status
        )

    # ==================== 获取用户视频 ====================

    def fetch_user_videos(self, user_url: str, output_file: str = None, page_size: int = 10) -> dict:
        """获取用户视频列表"""
        return self.fetcher.fetch_user_videos(user_url, output_file, page_size)

    # ==================== 标题和描述生成 ====================

    def generate_english_title(
        self,
        chinese_title: str,
        english_title: str = None,
        translate: bool = False
    ) -> str:
        """生成英文标题"""
        if english_title:
            return english_title

        if translate:
            return self.translate(chinese_title, "title")

        return chinese_title

    def generate_description(
        self,
        original_desc: str,
        source_url: str = "",
        uploader: str = "",
        translate: bool = False
    ) -> str:
        """生成视频描述"""
        lines = []

        if original_desc:
            if translate:
                translated_desc = self.translate(original_desc, "description")
                lines.append(translated_desc)
            else:
                lines.append(original_desc)
            lines.append("")

        lines.append("原创" if not translate else "Original Content")

        return "\n".join(lines)

    # ==================== 单视频搬运 ====================

    def transfer(
        self,
        xhs_url: str,
        title: str = None,
        description: str = None,
        english_title: str = None,
        custom_desc: str = None,
        tags: list = None,
        privacy: str = "public",
        keep_video: bool = False,
        translate: bool = False,
        translate_title: bool = True,
        translate_desc: bool = True,
        show_time_suggestion: bool = True
    ) -> dict:
        """完整的搬运流程"""
        self._log("=" * 60)
        self._log("小红书 → YouTube 视频搬运工具")
        if translate:
            self._log("[模式] 英文翻译模式")
        self._log("=" * 60)

        # 显示时间推荐并检查是否在推荐时段
        if show_time_suggestion:
            is_good_time, _ = self._show_time_suggestion()
            
            # 非推荐时段时询问确认
            if not is_good_time:
                self._log("")
                confirm = input("是否继续上传? [y/N]: ").strip().lower()
                if confirm != 'y':
                    self._log("[取消] 用户取消上传")
                    return {'success': False, 'error': 'user_cancelled', 'message': '用户取消上传'}

        # 1. 下载视频
        video_info = self.download_video(xhs_url, title, description)

        # 2. 生成标题和描述
        if translate and translate_title and not english_title:
            self._log("[翻译] 正在翻译标题...")
            title = self.generate_english_title(
                video_info['title'],
                english_title,
                translate=True
            )
        else:
            title = self.generate_english_title(video_info['title'], english_title)

        if custom_desc:
            description = custom_desc
        else:
            if translate and translate_desc:
                self._log("[翻译] 正在翻译描述...")
            description = self.generate_description(
                video_info['description'],
                xhs_url,
                video_info['uploader'],
                translate=translate and translate_desc
            )

        # 3. 上传到 YouTube
        result = self.upload_to_youtube(
            video_path=video_info['video_path'],
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy
        )

        # 4. 清理视频文件
        if not keep_video:
            try:
                os.remove(video_info['video_path'])
                self._log(f"[清理] 已删除本地视频文件")
            except Exception as e:
                self._log(f"[警告] 删除视频文件失败: {e}")

        self._log("=" * 60)
        self._log("搬运完成!")
        self._log("=" * 60)
        self._log(f"视频链接: {result['video_url']}")

        return result

    # ==================== 上传记录管理 ====================

    def _load_uploaded_records(self) -> Dict[str, Dict]:
        """加载已上传记录"""
        UPLOADED_FILE.parent.mkdir(parents=True, exist_ok=True)
        if UPLOADED_FILE.exists():
            try:
                with open(UPLOADED_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('records', {})
            except (json.JSONDecodeError, KeyError):
                return {}
        return {}

    def get_today_upload_count(self) -> int:
        """获取今日已上传数量"""
        records = self._load_uploaded_records()
        today = datetime.now().strftime("%Y-%m-%d")
        count = 0
        for record in records.values():
            uploaded_at = record.get('uploaded_at', '')
            if uploaded_at.startswith(today):
                count += 1
        return count

    def check_upload_limit(self) -> Dict[str, int]:
        """检查上传限制"""
        used = self.get_today_upload_count()
        return {
            'limit': DAILY_UPLOAD_LIMIT,
            'used': used,
            'remaining': max(0, DAILY_UPLOAD_LIMIT - used)
        }

    def _save_uploaded_record(self, record: UploadRecord) -> None:
        """保存上传记录"""
        UPLOADED_FILE.parent.mkdir(parents=True, exist_ok=True)
        records = self._load_uploaded_records()
        records[record.note_id] = {
            'youtube_id': record.youtube_id,
            'youtube_url': record.youtube_url,
            'title': record.title,
            'uploaded_at': record.uploaded_at
        }

        with open(UPLOADED_FILE, 'w', encoding='utf-8') as f:
            json.dump({'records': records}, f, ensure_ascii=False, indent=2)

    def _is_uploaded(self, note_id: str) -> Optional[Dict]:
        """检查视频是否已上传"""
        records = self._load_uploaded_records()
        return records.get(note_id)

    # ==================== 批量搬运 ====================

    def batch_transfer(
        self,
        video_list_path: str = None,
        interval_min: int = 10,
        interval_max: int = 30,
        privacy: str = "public",
        keep_video: bool = False,
        skip_uploaded: bool = True,
        translate: bool = False,
        translate_title: bool = True,
        translate_desc: bool = True
    ) -> Dict[str, Any]:
        """批量搬运视频"""
        from src.config import VIDEO_LIST_FILE

        self._log("=" * 60)
        self._log("小红书 → YouTube 批量搬运工具")
        self._log("=" * 60)

        # 1. 确定视频列表文件路径
        if video_list_path:
            list_path = Path(video_list_path)
        else:
            list_path = VIDEO_LIST_FILE

        if not list_path.exists():
            error_msg = f"视频列表文件不存在: {list_path}"
            self._log(f"[错误] {error_msg}")
            return {'success': False, 'error': error_msg}

        # 2. 加载视频列表
        self._log(f"[批量] 加载视频列表: {list_path}")
        with open(list_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        videos = data.get('videos', [])
        if not videos:
            self._log("[警告] 视频列表为空")
            return {'success': True, 'total': 0, 'skipped': 0, 'success_count': 0, 'failed': 0}

        self._log(f"[批量] 共 {len(videos)} 个视频待处理")

        # 3. 检查上传配额
        quota = self.check_upload_limit()
        self._log(f"[配额] 今日已上传 {quota['used']}/{quota['limit']} 个视频，剩余 {quota['remaining']} 个配额")

        if quota['remaining'] <= 0:
            self._log("[错误] 今日上传配额已用完，请明天再试")
            return {
                'success': False,
                'error': 'upload_limit_exceeded',
                'message': f"今日上传配额已用完 ({quota['limit']}个/天)",
                'total': len(videos),
                'skipped': 0,
                'success_count': 0,
                'failed': 0
            }

        # 4. 加载已上传记录
        uploaded_records = self._load_uploaded_records() if skip_uploaded else {}
        if uploaded_records:
            self._log(f"[批量] 已有 {len(uploaded_records)} 个上传记录")

        # 5. 统计信息
        results = {
            'success': True,
            'total': len(videos),
            'skipped': 0,
            'success_count': 0,
            'failed': 0,
            'failed_videos': []
        }

        # 6. 遍历处理
        for i, video in enumerate(videos):
            note_id = video.get('note_id', '')
            video_title = video.get('title', '')
            video_desc = video.get('desc', '')
            url = video.get('url', '')

            self._log("")
            self._log("-" * 50)
            self._log(f"[批量] 处理第 {i+1}/{len(videos)} 个: {video_title or '未知标题'}")

            # 检查是否已上传
            if skip_uploaded and note_id in uploaded_records:
                record = uploaded_records[note_id]
                self._log(f"[跳过] 已上传过: {record.get('youtube_url', '')}")
                results['skipped'] += 1
                continue

            # 检查是否有 URL
            if not url:
                self._log("[失败] 缺少视频 URL")
                results['failed'] += 1
                results['failed_videos'].append({
                    'note_id': note_id,
                    'title': video_title,
                    'error': '缺少视频 URL'
                })
                continue

            try:
                # 随机间隔
                if i > 0:
                    delay = random.randint(interval_min, interval_max)
                    self._log(f"[等待] {delay} 秒后继续...")
                    time.sleep(delay)

                # 执行搬运
                result = self.transfer(
                    xhs_url=url,
                    title=video_title,
                    description=video_desc,
                    privacy=privacy,
                    keep_video=keep_video,
                    translate=translate,
                    translate_title=translate_title,
                    translate_desc=translate_desc
                )

                # 记录上传结果
                record = UploadRecord(
                    note_id=note_id,
                    youtube_id=result['video_id'],
                    youtube_url=result['video_url'],
                    title=video_title or '未知标题',
                    uploaded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                self._save_uploaded_record(record)
                uploaded_records[note_id] = {
                    'youtube_id': record.youtube_id,
                    'youtube_url': record.youtube_url,
                    'title': record.title,
                    'uploaded_at': record.uploaded_at
                }

                results['success_count'] += 1
                self._log(f"[成功] 上传完成: {result['video_url']}")

            except Exception as e:
                error_msg = str(e)
                self._log(f"[失败] {video_title or '未知标题'}: {e}")
                results['failed'] += 1
                results['failed_videos'].append({
                    'note_id': note_id,
                    'title': video_title or '未知标题',
                    'error': error_msg
                })

                # 检测上传限制错误
                if 'uploadLimitExceeded' in error_msg:
                    self._log("")
                    self._log("[警告] YouTube 上传限制已达到，停止批量上传")
                    self._log(f"[提示] 今日上传配额已用完 ({DAILY_UPLOAD_LIMIT}个/天)，请明天再试")
                    results['limit_exceeded'] = True
                    break

        # 7. 输出统计
        self._log("")
        self._log("=" * 60)
        self._log("批量搬运完成!")
        self._log("=" * 60)
        self._log(f"总计: {results['total']} 个视频")
        self._log(f"成功: {results['success_count']} 个")
        self._log(f"跳过: {results['skipped']} 个")
        self._log(f"失败: {results['failed']} 个")

        if results['failed_videos']:
            self._log("")
            self._log("失败的视频:")
            for v in results['failed_videos']:
                self._log(f"  - {v['title']}: {v['error']}")

        return results

    # ==================== 时间推荐 ====================

    def _show_time_suggestion(self) -> tuple[bool, any]:
        """
        显示发布时间建议
        
        Returns:
            (is_good_time, recommendation) - 是否在推荐时段 + 推荐信息
        """
        from src.analyze import (
            analyze_and_cache,
            format_time_suggestion,
            get_time_recommendation,
            is_good_upload_time,
        )
        from datetime import datetime

        # 先尝试获取缓存
        recommendation = get_time_recommendation()

        # 如果没有缓存，尝试分析
        if not recommendation:
            cache = analyze_and_cache(log_callback=self._log)
            if cache:
                recommendation = cache.recommendation

        if recommendation:
            current_hour = datetime.now().hour
            suggestion = format_time_suggestion(recommendation, current_hour)
            self._log(suggestion)
            
            # 检查是否在推荐时段
            is_good, _ = is_good_upload_time(current_hour)
            return (is_good, recommendation)
        
        return (True, None)
