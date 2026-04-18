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
from src.spiritual_content import SpiritualContentClient


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
        self.spiritual_content = SpiritualContentClient(log_callback)

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
                
                # 设置安全权限：仅所有者可读写
                os.chmod(COOKIES_FILE, 0o600)

                return True
            except json.JSONDecodeError as e:
                self._log(f"[错误] JSON 解析失败: {e}")
                return False
        else:
            with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
                f.write(content + '\n')
            
            # 设置安全权限：仅所有者可读写
            os.chmod(COOKIES_FILE, 0o600)
            
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

    def _build_default_description(self, original_desc: str, translate: bool = False) -> str:
        lines = []

        if original_desc:
            lines.append(original_desc)
            lines.append("")

        lines.append("原创" if not translate else "Original Content")
        return "\n".join(lines)

    def _build_spiritual_description(self, spiritual, english: bool = False) -> str:
        lines = ["Spiritual Lines" if english else "属灵短句"]
        if spiritual.short_title:
            lines.append(spiritual.short_title)
        for line in spiritual.lines:
            lines.append(f"- {line}")
        if spiritual.references:
            refs = "；".join(spiritual.references[:2])
            lines.append(f"{'References' if english else '参考'}：{refs}")
        return "\n".join(lines).strip()

    def generate_description(
        self,
        original_desc: str,
        source_url: str = "",
        uploader: str = "",
        translate: bool = False
    ) -> str:
        """生成视频描述"""
        context = source_url or uploader or ""
        spiritual = None
        if translate:
            spiritual = self.spiritual_content.compose(
                text=original_desc or "",
                tags=[],
                context=context,
                length=4,
                target_lang="en",
            )
        if spiritual is None:
            spiritual = self.spiritual_content.compose(
                text=original_desc or "",
                tags=[],
                context=context,
                length=4,
            )

        if translate and spiritual and spiritual.lines:
            spiritual_desc = self._build_spiritual_description(spiritual, english=True)
            if spiritual_desc:
                return spiritual_desc

        base_description = self._build_default_description(original_desc, translate=False)
        if spiritual and spiritual.lines:
            spiritual_desc = self._build_spiritual_description(spiritual)
            if spiritual_desc:
                base_description = spiritual_desc

        if translate:
            translated = self.translate(base_description, "description")
            if translated and translated.strip():
                return translated

        return base_description if base_description else self._build_default_description(original_desc, translate=translate)

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

        # 5. 保存上传记录
        upload_hour = datetime.now().hour
        time_slot, followed = self._get_time_slot_info(upload_hour)
        
        note_id = video_info.get('note_id', '')
        if note_id:
            record = UploadRecord(
                note_id=note_id,
                youtube_id=result['video_id'],
                youtube_url=result['video_url'],
                title=title,
                uploaded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                upload_hour=upload_hour,
                time_slot=time_slot,
                recommendation_followed=followed,
            )
            self._save_uploaded_record(record)

        self._log("=" * 60)
        self._log("搬运完成!")
        self._log("=" * 60)
        self._log(f"视频链接: {result['video_url']}")

        # 返回结果包含翻译后的标题
        result['title'] = title
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
            'uploaded_at': record.uploaded_at,
            'upload_hour': record.upload_hour,
            'time_slot': record.time_slot,
            'recommendation_followed': record.recommendation_followed,
        }

        with open(UPLOADED_FILE, 'w', encoding='utf-8') as f:
            json.dump({'records': records}, f, ensure_ascii=False, indent=2)

    def _is_uploaded(self, note_id: str) -> Optional[Dict]:
        """检查视频是否已上传"""
        records = self._load_uploaded_records()
        return records.get(note_id)

    def _get_time_slot_info(self, upload_hour: int) -> tuple[str, bool]:
        """
        获取上传时间段标签
        
        Returns:
            (time_slot, followed_recommendation) 元组
        """
        from src.analyze import get_time_recommendation
        
        recommendation = get_time_recommendation()
        if not recommendation:
            return "未知", True
        
        # 解析推荐时段
        def parse_time(time_str: str) -> tuple[int, int]:
            parts = time_str.split("-")
            start = int(parts[0].split(":")[0])
            end = int(parts[1].split(":")[0])
            return start, end
        
        optimal_start, optimal_end = parse_time(recommendation.optimal_time)
        secondary_start, secondary_end = parse_time(recommendation.secondary_time)
        
        # 判断当前时段
        if optimal_start <= upload_hour < optimal_end:
            return "黄金时段", True
        elif secondary_start <= upload_hour < secondary_end:
            return "次选时段", True
        else:
            return "非推荐时段", False

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
        translate_desc: bool = True,
        limit: int = 0,
        show_time_suggestion: bool = False,
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

        total_videos = len(videos)
        
        # 显示 limit 信息（实际限制在成功上传时计数）
        if limit > 0:
            self._log(f"[限制] 本次将实际上传最多 {limit} 个视频（跳过已上传）")
        
        self._log(f"[批量] 共 {total_videos} 个视频待处理")

        # 3. 检查上传配额
        quota = self.check_upload_limit()
        self._log(f"[配额] 今日已上传 {quota['used']}/{quota['limit']} 个视频，剩余 {quota['remaining']} 个配额")

        if quota['remaining'] <= 0:
            self._log("[错误] 今日上传配额已用完，请明天再试")
            return {
                'success': False,
                'error': 'upload_limit_exceeded',
                'message': f"今日上传配额已用完 ({quota['limit']}个/天)",
                'total': total_videos,
                'skipped': 0,
                'success_count': 0,
                'failed': 0
            }

        # 4. 加载已上传记录并预过滤待处理队列
        uploaded_records = self._load_uploaded_records() if skip_uploaded else {}
        pending_videos = videos
        skipped_existing = 0

        if uploaded_records:
            self._log(f"[批量] 已有 {len(uploaded_records)} 个上传记录")

        if skip_uploaded and uploaded_records:
            pending_videos = []
            for video in videos:
                note_id = video.get('note_id', '')
                if note_id and note_id in uploaded_records:
                    skipped_existing += 1
                    continue
                pending_videos.append(video)

            if skipped_existing:
                self._log(
                    f"[批量] 已过滤 {skipped_existing} 个已上传视频，"
                    f"剩余 {len(pending_videos)} 个待处理"
                )

        # 5. 统计信息
        results = {
            'success': True,
            'total': total_videos,
            'skipped': skipped_existing,
            'success_count': 0,
            'failed': 0,
            'failed_videos': []
        }

        # 6. 遍历处理
        for i, video in enumerate(pending_videos):
            note_id = video.get('note_id', '')
            video_title = video.get('title', '')
            video_desc = video.get('desc', '')
            url = video.get('url', '')

            self._log("")
            self._log("-" * 50)
            self._log(
                f"[批量] 处理第 {i+1}/{len(pending_videos)} 个待处理视频: "
                f"{video_title or '未知标题'}"
            )

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
                    translate_desc=translate_desc,
                    show_time_suggestion=show_time_suggestion,
                )

                # 记录上传结果
                upload_hour = datetime.now().hour
                time_slot, followed = self._get_time_slot_info(upload_hour)
                
                # 使用翻译后的标题（如果有），否则使用原始标题
                final_title = result.get('title', video_title) or '未知标题'
                record = UploadRecord(
                    note_id=note_id,
                    youtube_id=result['video_id'],
                    youtube_url=result['video_url'],
                    title=final_title,
                    uploaded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    upload_hour=upload_hour,
                    time_slot=time_slot,
                    recommendation_followed=followed,
                )
                self._save_uploaded_record(record)
                uploaded_records[note_id] = {
                    'youtube_id': record.youtube_id,
                    'youtube_url': record.youtube_url,
                    'title': record.title,
                    'uploaded_at': record.uploaded_at,
                    'upload_hour': upload_hour,
                    'time_slot': time_slot,
                    'recommendation_followed': followed,
                }

                results['success_count'] += 1
                self._log(f"[成功] 上传完成: {result['video_url']}")
                
                # 检查是否达到上传数量限制
                if limit > 0 and results['success_count'] >= limit:
                    self._log(f"[限制] 已达到上传数量限制 ({limit} 个)，停止批量上传")
                    break

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

        results['success'] = results['failed'] == 0
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
