"""
视频下载模块
处理小红书视频下载、无水印视频流选择
"""

import json
import re
import codecs
import uuid
import os
from pathlib import Path
from typing import Dict, Optional, Callable

import requests

from src.config import COOKIES_FILE, VIDEOS_DIR
from src.translate import TranslateService


# ==================== 自定义异常类 ====================

class DownloadError(Exception):
    """下载失败基础异常"""
    pass


class VideoNotFoundError(DownloadError):
    """视频未找到异常（可能是图文笔记或需要登录）"""
    pass


class NetworkTimeoutError(DownloadError):
    """网络超时异常"""
    pass


class NetworkConnectionError(DownloadError):
    """网络连接失败异常"""
    pass


class CookieLoadError(DownloadError):
    """Cookie 加载失败异常"""
    pass


# ==================== 视频下载器 ====================

class VideoDownloader:
    """视频下载器"""

    def __init__(
        self,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.translate_service = TranslateService(log_callback)
        self._current_video_path: Optional[Path] = None

    def _log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        print(message)

    def _progress(self, value: float, status: str = ""):
        if self.progress_callback:
            self.progress_callback(value, status)

    def _cleanup_partial_file(self, video_path: Optional[Path] = None):
        """清理部分下载的文件"""
        path_to_clean = video_path or self._current_video_path
        if path_to_clean and path_to_clean.exists():
            try:
                os.remove(path_to_clean)
                self._log(f"[清理] 已删除部分下载文件: {path_to_clean}")
            except OSError as e:
                self._log(f"[警告] 删除部分文件失败: {e}")

    def _load_cookies(self) -> Dict[str, str]:
        """加载小红书 Cookie"""
        cookies = {}
        if not COOKIES_FILE.exists():
            self._log("[警告] Cookie 文件不存在，可能无法访问需要登录的内容")
            return cookies
        
        try:
            with open(COOKIES_FILE, encoding='utf-8') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        cookies[parts[5]] = parts[6]
        except (IOError, PermissionError) as e:
            self._log(f"[警告] 读取 Cookie 文件失败: {e}")
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(COOKIES_FILE, encoding='gbk') as f:
                    for line in f:
                        if line.startswith('#') or not line.strip():
                            continue
                        parts = line.strip().split('\t')
                        if len(parts) >= 7:
                            cookies[parts[5]] = parts[6]
            except (OSError, PermissionError, UnicodeDecodeError, LookupError) as e:
                self._log(f"[警告] Cookie 文件编码问题: {e}")
        
        return cookies

    def _get_headers(self) -> Dict[str, str]:
        """获取默认请求头"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def _extract_title(self, html: str, fallback_title: str = None) -> str:
        """
        从 HTML 中提取标题
        
        Args:
            html: HTML 内容
            fallback_title: 备选标题
            
        Returns:
            提取的标题，确保非空
        """
        title = fallback_title
        
        # 方法1: 从 <title> 标签提取
        if not title:
            html_title_match = re.search(r'<title>([^<]+)</title>', html)
            if html_title_match:
                html_title = html_title_match.group(1)
                if ' - 小红书' in html_title:
                    title = html_title.split(' - 小红书')[0].strip()
                elif '小红书' in html_title and len(html_title) > 10:
                    title = html_title.replace(' - 小红书', '').replace('小红书', '').strip()
                else:
                    title = html_title.strip()
        
        # 方法2: 从 displayTitle 提取
        if not title or title == "未知标题" or 'ICP' in title:
            title_match = re.search(r'"displayTitle"\s*:\s*"([^"]*)"', html)
            if title_match and title_match.group(1):
                title = title_match.group(1)
        
        # 确保返回非空值
        return title if title and title.strip() else "未知标题"

    def _select_best_video_stream(self, page_text: str) -> tuple:
        """
        从页面内容中提取视频流并选择最佳（无水印）版本
        """
        streams = []

        # 解析 h264 流
        h264_pattern = r'"h264"\s*:\s*\[(.*?)\](?=\s*,\s*"h265"|\s*\})'
        h264_match = re.search(h264_pattern, page_text, re.DOTALL)
        if h264_match:
            h264_text = h264_match.group(1)
            url_pattern = r'"masterUrl"\s*:\s*"([^"]+)"'
            desc_pattern = r'"streamDesc"\s*:\s*"([^"]+)"'
            urls = re.findall(url_pattern, h264_text)
            descs = re.findall(desc_pattern, h264_text)

            for url, desc in zip(urls, descs):
                decoded_url = codecs.decode(url, 'unicode_escape')
                has_watermark = desc.startswith('WM') or 'WM_' in desc
                streams.append({
                    'url': decoded_url,
                    'desc': desc,
                    'codec': 'h264',
                    'has_watermark': has_watermark
                })

        # 解析 h265 流
        h265_pattern = r'"h265"\s*:\s*\[(.*?)\](?=\s*,\s*"av1"|\s*,\s*"h266"|\s*\})'
        h265_match = re.search(h265_pattern, page_text, re.DOTALL)
        if h265_match:
            h265_text = h265_match.group(1)
            url_pattern = r'"masterUrl"\s*:\s*"([^"]+)"'
            desc_pattern = r'"streamDesc"\s*:\s*"([^"]+)"'
            urls = re.findall(url_pattern, h265_text)
            descs = re.findall(desc_pattern, h265_text)

            for url, desc in zip(urls, descs):
                decoded_url = codecs.decode(url, 'unicode_escape')
                has_watermark = desc.startswith('WM') or 'WM_' in desc
                streams.append({
                    'url': decoded_url,
                    'desc': desc,
                    'codec': 'h265',
                    'has_watermark': has_watermark
                })

        if not streams:
            return None, ""

        # 优先选择无水印版本
        no_watermark_streams = [s for s in streams if not s['has_watermark']]

        if no_watermark_streams:
            best = no_watermark_streams[0]
            info = f"{best['codec']} 无水印版本 ({best['desc']})"
            self._log(f"[下载] 找到无水印视频流: {best['desc']}")
            return best['url'], info

        best = streams[0]
        info = f"{best['codec']} ({best['desc']})"
        self._log(f"[下载] 未找到无水印版本，使用: {best['desc']}")
        return best['url'], info

    def download_video(self, url: str, title: str = None, description: str = None) -> dict:
        """
        下载小红书视频
        
        Args:
            url: 小红书视频 URL
            title: 标题（可选）
            description: 描述（可选）
            
        Returns:
            包含视频信息的字典
            
        Raises:
            VideoNotFoundError: 视频未找到（可能是图文笔记）
            NetworkTimeoutError: 网络超时
            NetworkConnectionError: 网络连接失败
            DownloadError: 其他下载错误
        """
        self._log("=" * 50)
        self._log("[下载] 开始下载小红书视频...")
        self._log("=" * 50)
        self._progress(0, "开始下载...")

        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

        cookies = self._load_cookies()
        self._log(f"[下载] 已加载 {len(cookies)} 个 Cookie")

        headers = self._get_headers()
        video_path = None

        try:
            self._log(f"[下载] 获取视频信息: {url}")
            self._progress(5, "获取视频信息...")

            # 从 URL 中提取 note_id（视频 ID 是 URL 中最后一个 24 位 hex）
            # URL 格式: /user/profile/{user_id}/{note_id}?xsec_token=...
            note_id_match = re.search(r'/([a-f0-9]{24})(?:\?|$|/)', url)
            note_id = note_id_match.group(1) if note_id_match else ''

            # 获取页面内容
            try:
                resp = requests.get(url, cookies=cookies, headers=headers, allow_redirects=True, timeout=30)
            except requests.Timeout:
                self._log("[错误] 请求超时，请检查网络连接")
                raise NetworkTimeoutError("获取视频信息超时，请检查网络连接")
            except requests.ConnectionError as e:
                self._log(f"[错误] 网络连接失败: {e}")
                raise NetworkConnectionError("网络连接失败，请检查网络设置")

            video_title = self._extract_title(resp.text, title)
            video_desc = description
            duration = 0

            if not video_desc:
                desc_match = re.search(r'"desc"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', resp.text)
                if desc_match:
                    video_desc = desc_match.group(1)

            duration_match = re.search(r'"duration"\s*:\s*(\d+)', resp.text)
            if duration_match:
                duration_value = int(duration_match.group(1))
                duration = duration_value if duration_value < 1000 else duration_value // 1000

            video_url, video_info = self._select_best_video_stream(resp.text)

            if not video_url:
                self._log("[错误] 未找到视频链接")
                self._log("可能的原因:")
                self._log("  1. 该链接是图文笔记，不是视频")
                self._log("  2. Cookie 已过期，需要更新")
                self._log("  3. 视频需要登录才能访问")
                self._log("提示: 运行 'xhs2yt update --cookie' 更新 Cookie")
                raise VideoNotFoundError("未找到视频链接，请确认链接是视频内容")

            self._log(f"[下载] 标题: {video_title}")
            self._log(f"[下载] 选择视频流: {video_info}")

            self._progress(10, "开始下载视频...")

            # 下载视频文件
            try:
                video_resp = requests.get(video_url, stream=True, timeout=120)
            except requests.Timeout:
                self._log("[错误] 视频下载超时")
                raise NetworkTimeoutError("视频下载超时，请稍后重试")
            except requests.ConnectionError as e:
                self._log(f"[错误] 视频下载连接失败: {e}")
                raise NetworkConnectionError("视频下载连接失败，请检查网络设置")

            total_size = int(video_resp.headers.get('content-length', 0))

            video_id = str(uuid.uuid4())[:8]
            video_path = VIDEOS_DIR / f"{video_id}.mp4"
            self._current_video_path = video_path

            downloaded = 0
            try:
                with open(video_path, 'wb') as f:
                    for chunk in video_resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size:
                                progress = 10 + (downloaded / total_size) * 40
                                self._progress(progress, f"下载中... {int(downloaded/total_size*100)}%")
            except (OSError, ValueError, TypeError) as e:
                self._cleanup_partial_file(video_path)
                raise DownloadError(f"视频文件写入失败: {e}")

            self._log(f"[下载] 下载完成!")
            self._log(f"  - 文件: {video_path}")
            self._log(f"  - 大小: {downloaded / 1024 / 1024:.2f} MB")

            self._current_video_path = None
            return {
                'video_path': str(video_path),
                'title': video_title,
                'description': video_desc or '',
                'uploader': '',
                'duration': duration,
                'note_id': note_id,
            }

        except (VideoNotFoundError, NetworkTimeoutError, NetworkConnectionError, DownloadError):
            # 这些是我们定义的异常，直接重新抛出
            raise
        except requests.Timeout:
            self._log("[错误] 请求超时")
            self._cleanup_partial_file(video_path)
            raise NetworkTimeoutError("请求超时，请检查网络连接")
        except requests.ConnectionError as e:
            self._log(f"[错误] 网络连接失败: {e}")
            self._cleanup_partial_file(video_path)
            raise NetworkConnectionError("网络连接失败，请检查网络设置")
        except (requests.RequestException, OSError, ValueError, TypeError, KeyError) as e:
            self._log(f"[错误] 下载失败: {e}")
            self._cleanup_partial_file(video_path)
            raise DownloadError(f"下载失败: {e}")
