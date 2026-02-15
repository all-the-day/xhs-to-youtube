#!/usr/bin/env python3
"""
小红书到 YouTube 视频搬运核心逻辑
支持进度回调和日志回调，可被 CLI 和 GUI 共同调用
"""

import json
import os
import sys
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass

# YouTube API 相关导入
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("请先安装 Google API 客户端库:")
    print("pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")
    sys.exit(1)

# 配置
SCRIPT_DIR = Path(__file__).parent.absolute()
COOKIES_FILE = SCRIPT_DIR / "cookies.txt"
CREDENTIALS_FILE = SCRIPT_DIR / "credentials.json"
TOKEN_FILE = SCRIPT_DIR / "token.json"
VIDEOS_DIR = SCRIPT_DIR / "videos"

# YouTube API 权限范围
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


@dataclass
class CredentialStatus:
    """凭证状态"""
    name: str
    exists: bool
    valid: bool
    message: str
    path: str


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
        """
        初始化
        
        Args:
            log_callback: 日志回调函数，接收日志消息
            progress_callback: 进度回调函数，接收 (进度值, 状态描述)
        """
        self.youtube_service = None
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self._flow = None  # 存储 OAuth flow 对象，用于 Web UI 授权
    
    def _log(self, message: str):
        """输出日志"""
        if self.log_callback:
            self.log_callback(message)
        print(message)
    
    def _progress(self, value: float, status: str = ""):
        """更新进度"""
        if self.progress_callback:
            self.progress_callback(value, status)
    
    def check_credentials(self) -> Dict[str, CredentialStatus]:
        """
        检查所有凭证状态
        
        Returns:
            包含各项凭证状态的字典
        """
        statuses = {}
        
        # 检查 Cookie 文件
        if COOKIES_FILE.exists():
            content = COOKIES_FILE.read_text().strip()
            if content and not content.startswith('#'):
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
        
        # 检查 Google 凭证文件
        if CREDENTIALS_FILE.exists():
            try:
                content = json.loads(CREDENTIALS_FILE.read_text())
                if 'installed' in content or 'web' in content:
                    statuses['credentials'] = CredentialStatus(
                        name="Google OAuth 凭证",
                        exists=True,
                        valid=True,
                        message="已配置",
                        path=str(CREDENTIALS_FILE)
                    )
                else:
                    statuses['credentials'] = CredentialStatus(
                        name="Google OAuth 凭证",
                        exists=True,
                        valid=False,
                        message="格式不正确",
                        path=str(CREDENTIALS_FILE)
                    )
            except json.JSONDecodeError:
                statuses['credentials'] = CredentialStatus(
                    name="Google OAuth 凭证",
                    exists=True,
                    valid=False,
                    message="JSON 格式错误",
                    path=str(CREDENTIALS_FILE)
                )
        else:
            statuses['credentials'] = CredentialStatus(
                name="Google OAuth 凭证",
                exists=False,
                valid=False,
                message="文件不存在",
                path=str(CREDENTIALS_FILE)
            )
        
        # 检查 Token 文件
        if TOKEN_FILE.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
                if creds.valid:
                    statuses['token'] = CredentialStatus(
                        name="YouTube Token",
                        exists=True,
                        valid=True,
                        message="有效",
                        path=str(TOKEN_FILE)
                    )
                elif creds.expired and creds.refresh_token:
                    statuses['token'] = CredentialStatus(
                        name="YouTube Token",
                        exists=True,
                        valid=False,
                        message="已过期，需要刷新",
                        path=str(TOKEN_FILE)
                    )
                else:
                    statuses['token'] = CredentialStatus(
                        name="YouTube Token",
                        exists=True,
                        valid=False,
                        message="无效",
                        path=str(TOKEN_FILE)
                    )
            except Exception as e:
                statuses['token'] = CredentialStatus(
                    name="YouTube Token",
                    exists=True,
                    valid=False,
                    message=f"读取失败: {str(e)[:30]}",
                    path=str(TOKEN_FILE)
                )
        else:
            statuses['token'] = CredentialStatus(
                name="YouTube Token",
                exists=False,
                valid=False,
                message="未授权（首次使用会自动生成）",
                path=str(TOKEN_FILE)
            )
        
        return statuses

    def _select_best_video_stream(self, page_text: str) -> tuple:
        """
        从页面内容中提取视频流并选择最佳（无水印）版本
        
        Args:
            page_text: 页面 HTML 内容
            
        Returns:
            (video_url, stream_info): 视频URL和流信息描述
        """
        import codecs
        
        streams = []
        
        # 解析 h264 流
        h264_pattern = r'"h264"\s*:\s*\[(.*?)\](?=\s*,\s*"h265"|\s*\})'
        h264_match = __import__('re').search(h264_pattern, page_text, __import__('re').DOTALL)
        if h264_match:
            h264_text = h264_match.group(1)
            # 提取每个流的 URL 和描述
            url_pattern = r'"masterUrl"\s*:\s*"([^"]+)"'
            desc_pattern = r'"streamDesc"\s*:\s*"([^"]+)"'
            urls = __import__('re').findall(url_pattern, h264_text)
            descs = __import__('re').findall(desc_pattern, h264_text)
            
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
        h265_match = __import__('re').search(h265_pattern, page_text, __import__('re').DOTALL)
        if h265_match:
            h265_text = h265_match.group(1)
            url_pattern = r'"masterUrl"\s*:\s*"([^"]+)"'
            desc_pattern = r'"streamDesc"\s*:\s*"([^"]+)"'
            urls = __import__('re').findall(url_pattern, h265_text)
            descs = __import__('re').findall(desc_pattern, h265_text)
            
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
            # 选择第一个无水印流
            best = no_watermark_streams[0]
            info = f"{best['codec']} 无水印版本 ({best['desc']})"
            self._log(f"[下载] 找到无水印视频流: {best['desc']}")
            return best['url'], info
        
        # 如果没有无水印版本，使用第一个可用流
        best = streams[0]
        info = f"{best['codec']} ({best['desc']})"
        self._log(f"[下载] 未找到无水印版本，使用: {best['desc']}")
        return best['url'], info

    def download_video(self, url: str) -> dict:
        """
        下载小红书视频（使用自定义下载方法）
        返回包含视频路径、标题、描述的字典
        """
        import requests
        import codecs
        import uuid
        
        self._log("=" * 50)
        self._log("[下载] 开始下载小红书视频...")
        self._log("=" * 50)
        self._progress(0, "开始下载...")
        
        # 确保视频目录存在
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        
        # 读取 Cookie
        cookies = {}
        if COOKIES_FILE.exists():
            with open(COOKIES_FILE) as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        cookies[parts[5]] = parts[6]
            self._log(f"[下载] 已加载 {len(cookies)} 个 Cookie")
        else:
            self._log(f"[警告] 未找到 Cookie 文件: {COOKIES_FILE}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            # 获取页面内容
            self._log(f"[下载] 获取视频信息: {url}")
            self._progress(5, "获取视频信息...")
            
            resp = requests.get(url, cookies=cookies, headers=headers, allow_redirects=True, timeout=30)
            
            # 提取视频信息
            title = "未知标题"
            desc = ""
            duration = 0
            
            # 提取标题
            title_match = __import__('re').search(r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', resp.text)
            if title_match:
                title = title_match.group(1)
                # 过滤掉页面标题
                if 'ICP' in title or '小红书' in title:
                    title = "未知标题"
            
            # 提取描述
            desc_match = __import__('re').search(r'"desc"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', resp.text)
            if desc_match:
                desc = desc_match.group(1)
            
            # 提取时长（小红书的 duration 可能是秒或毫秒）
            duration_match = __import__('re').search(r'"duration"\s*:\s*(\d+)', resp.text)
            if duration_match:
                duration_value = int(duration_match.group(1))
                # 如果值大于 1000，则认为是毫秒，需要转换为秒
                duration = duration_value if duration_value < 1000 else duration_value // 1000
            
            # 提取视频流并选择无水印版本
            video_url, video_info = self._select_best_video_stream(resp.text)
            
            if not video_url:
                self._log("[错误] 未找到视频链接，可能是图文笔记或需要登录")
                raise Exception("未找到视频链接，请确认链接是视频内容")
            
            self._log(f"[下载] 标题: {title}")
            self._log(f"[下载] 选择视频流: {video_info}")
            
            # 下载视频
            self._progress(10, "开始下载视频...")
            
            video_resp = requests.get(video_url, stream=True, timeout=120)
            total_size = int(video_resp.headers.get('content-length', 0))
            
            # 生成唯一文件名
            video_id = str(uuid.uuid4())[:8]
            video_path = VIDEOS_DIR / f"{video_id}.mp4"
            
            downloaded = 0
            with open(video_path, 'wb') as f:
                for chunk in video_resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            # 下载进度占 10% 到 50%
                            progress = 10 + (downloaded / total_size) * 40
                            self._progress(progress, f"下载中... {int(downloaded/total_size*100)}%")
            
            self._log(f"[下载] 下载完成!")
            self._log(f"  - 文件: {video_path}")
            self._log(f"  - 大小: {downloaded / 1024 / 1024:.2f} MB")
            
            result = {
                'video_path': str(video_path),
                'title': title,
                'description': desc,
                'uploader': '',
                'duration': duration,
            }
            
            return result
            
        except Exception as e:
            self._log(f"[错误] 下载失败: {e}")
            raise

    def get_youtube_service(self):
        """
        获取 YouTube API 服务实例
        处理 OAuth 认证流程
        """
        if self.youtube_service:
            return self.youtube_service
        
        self._log("=" * 50)
        self._log("[认证] 初始化 YouTube API...")
        self._log("=" * 50)
        
        creds = None
        
        # 检查是否已有有效的 token
        if TOKEN_FILE.exists():
            self._log(f"[认证] 发现已有 token 文件")
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        
        # 如果没有有效凭证，进行授权
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self._log("[认证] Token 已过期，正在刷新...")
                self._progress(55, "刷新认证 Token...")
                creds.refresh(Request())
            else:
                # 检查 credentials.json
                if not CREDENTIALS_FILE.exists():
                    error_msg = f"未找到 OAuth 凭证文件: {CREDENTIALS_FILE}"
                    self._log(f"[错误] {error_msg}")
                    raise FileNotFoundError(error_msg)
                
                self._log("[认证] 启动 OAuth 授权流程...")
                self._log("[认证] 浏览器将打开授权页面，请登录 Google 账号并授权")
                self._progress(55, "等待浏览器授权...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_FILE), SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # 保存凭证
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            self._log(f"[认证] 凭证已保存到: {TOKEN_FILE}")
        
        # 创建 YouTube 服务
        self.youtube_service = build('youtube', 'v3', credentials=creds)
        self._log("[认证] YouTube API 初始化成功!")
        
        return self.youtube_service

    def get_authorization_url(self) -> tuple:
        """
        获取 YouTube OAuth 授权 URL（用于 Web UI）
        
        Returns:
            (success: bool, url_or_message: str)
            - 成功时返回 (True, authorization_url)
            - 失败时返回 (False, error_message)
        """
        self._log("=" * 50)
        self._log("[授权] 生成 YouTube OAuth 授权 URL...")
        self._log("=" * 50)
        
        # 检查 credentials.json
        if not CREDENTIALS_FILE.exists():
            error_msg = f"未找到 OAuth 凭证文件: {CREDENTIALS_FILE}\n请先从 Google Cloud Console 下载 credentials.json"
            self._log(f"[错误] {error_msg}")
            return False, error_msg
        
        try:
            # 读取凭证文件
            with open(CREDENTIALS_FILE, 'r') as f:
                client_config = json.load(f)
            
            # 修改 redirect_uris 为手动授权方式
            # urn:ietf:wg:oauth:2.0:oob 是 Google 支持的命令行授权重定向方式
            if 'installed' in client_config:
                client_config['installed']['redirect_uris'] = ['urn:ietf:wg:oauth:2.0:oob']
            elif 'web' in client_config:
                client_config['web']['redirect_uris'] = ['urn:ietf:wg:oauth:2.0:oob']
            
            # 创建 flow 对象
            self._flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            
            # 手动设置 redirect_uri（InstalledAppFlow 不会自动设置）
            self._flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
            
            # 生成授权 URL
            auth_url, _ = self._flow.authorization_url(
                access_type='offline',
                prompt='consent'
            )
            
            self._log("[授权] 授权 URL 生成成功")
            self._log(f"[授权] 请复制以下 URL 到浏览器完成授权:")
            self._log(auth_url)
            
            return True, auth_url
            
        except Exception as e:
            error_msg = f"生成授权 URL 失败: {str(e)}"
            self._log(f"[错误] {error_msg}")
            self._flow = None
            return False, error_msg

    def authorize_youtube_with_code(self, code: str) -> tuple:
        """
        使用授权码完成 YouTube OAuth 授权（用于 Web UI）
        
        Args:
            code: 用户从浏览器获取的授权码
            
        Returns:
            (success: bool, message: str)
        """
        self._log("=" * 50)
        self._log("[授权] 使用授权码完成 YouTube OAuth 授权...")
        self._log("=" * 50)
        
        # 检查是否有有效的 flow 对象
        if not self._flow:
            error_msg = "未找到授权会话，请先获取授权 URL"
            self._log(f"[错误] {error_msg}")
            return False, error_msg
        
        try:
            # 使用授权码交换凭证
            # 注意：Google 可能返回额外的 scope，跳过验证
            self._flow.fetch_token(code=code)
            creds = self._flow.credentials
            
            # 保存凭证
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            
            success_msg = f"授权成功！凭证已保存到: {TOKEN_FILE}"
            self._log(f"[授权] {success_msg}")
            
            # 清理 flow 对象
            self._flow = None
            
            return True, success_msg
            
        except Exception as e:
            error_msg = f"授权失败: {str(e)}"
            self._log(f"[错误] {error_msg}")
            return False, error_msg

    def authorize_youtube(self) -> tuple:
        """
        手动进行 YouTube OAuth 授权
        返回 (success: bool, message: str)
        """
        self._log("=" * 50)
        self._log("[授权] 开始 YouTube OAuth 授权流程...")
        self._log("=" * 50)
        
        # 检查 credentials.json
        if not CREDENTIALS_FILE.exists():
            error_msg = f"未找到 OAuth 凭证文件: {CREDENTIALS_FILE}\n请先从 Google Cloud Console 下载 credentials.json"
            self._log(f"[错误] {error_msg}")
            return False, error_msg
        
        try:
            self._log("[授权] 浏览器将打开授权页面...")
            self._log("[授权] 请登录 Google 账号并授权应用访问 YouTube")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
            
            # 保存凭证
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            
            success_msg = f"授权成功！凭证已保存到: {TOKEN_FILE}"
            self._log(f"[授权] {success_msg}")
            return True, success_msg
            
        except Exception as e:
            error_msg = f"授权失败: {str(e)}"
            self._log(f"[错误] {error_msg}")
            return False, error_msg

    def upload_to_youtube(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list = None,
        category_id: str = "22",
        privacy_status: str = "public"
    ) -> dict:
        """
        上传视频到 YouTube
        """
        self._log("=" * 50)
        self._log("[上传] 开始上传到 YouTube...")
        self._log("=" * 50)
        self._log(f"  - 标题: {title}")
        self._log(f"  - 隐私: {privacy_status}")
        self._progress(60, "准备上传...")
        
        youtube = self.get_youtube_service()
        
        # 准备视频元数据
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags or [],
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }
        
        # 准备上传
        media = MediaFileUpload(
            video_path,
            chunksize=1024 * 1024,
            resumable=True,
            mimetype='video/*'
        )
        
        # 执行上传
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                # 上传进度从 60% 到 100%
                progress = 60 + status.progress() * 40
                self._progress(progress, f"上传中... {int(status.progress() * 100)}%")
        
        self._log("[上传] 上传完成!")
        
        video_id = response['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        self._log(f"  - 视频ID: {video_id}")
        self._log(f"  - 视频链接: {video_url}")
        
        self._progress(100, "完成!")
        
        return {
            'video_id': video_id,
            'video_url': video_url,
            'response': response
        }

    def generate_bilingual_title(self, chinese_title: str, english_title: str = None) -> str:
        """生成双语标题"""
        if english_title:
            return f"【{chinese_title}】{english_title}"
        return chinese_title

    def generate_description(
        self,
        original_desc: str,
        source_url: str = "",
        uploader: str = ""
    ) -> str:
        """生成视频描述"""
        lines = []
        
        if original_desc:
            lines.append(original_desc)
            lines.append("")
        
        lines.append("原创")
        
        return "\n".join(lines)

    def transfer(
        self,
        xhs_url: str,
        english_title: str = None,
        custom_desc: str = None,
        tags: list = None,
        privacy: str = "public",
        keep_video: bool = False
    ) -> dict:
        """
        完整的搬运流程
        """
        self._log("=" * 60)
        self._log("小红书 → YouTube 视频搬运工具")
        self._log("=" * 60)
        
        # 1. 下载视频
        video_info = self.download_video(xhs_url)
        
        # 2. 生成标题和描述
        title = self.generate_bilingual_title(video_info['title'], english_title)
        
        if custom_desc:
            description = custom_desc
        else:
            description = self.generate_description(
                video_info['description'],
                xhs_url,
                video_info['uploader']
            )
        
        # 3. 上传到 YouTube
        result = self.upload_to_youtube(
            video_path=video_info['video_path'],
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy
        )
        
        # 4. 清理视频文件（可选）
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
