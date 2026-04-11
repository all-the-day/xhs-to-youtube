"""
YouTube 上传模块
处理 OAuth 认证和视频上传
"""

import json
import sys
from pathlib import Path
from typing import Callable, Optional

from src.config import CREDENTIALS_FILE, TOKEN_FILE, SCOPES, load_config
AUTH_SESSION_FILE = TOKEN_FILE.with_name("youtube_auth_session.json")
from src.models import CredentialStatus

# YouTube API 相关导入
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
except ImportError:
    print("请先安装 Google API 客户端库:")
    print("pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")
    sys.exit(1)


# ==================== 自定义异常类 ====================

class UploadError(Exception):
    """上传失败基础异常"""
    pass


class QuotaExceededError(UploadError):
    """YouTube 上传配额超限异常"""
    pass


class VideoValidationError(UploadError):
    """视频验证失败异常"""
    pass


class AuthenticationError(UploadError):
    """认证失败异常"""
    pass


class AuthorizationError(UploadError):
    """授权失败异常"""
    pass


# ==================== YouTube 上传器 ====================

class YouTubeUploader:
    """YouTube 上传器"""

    def __init__(
        self,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ):
        self.youtube_service = None
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self._flow = None

    def _log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        print(message)

    def _progress(self, value: float, status: str = ""):
        if self.progress_callback:
            self.progress_callback(value, status)

    def check_credentials(self) -> dict:
        """检查凭证状态"""
        statuses = {}

        # Cookie 检查由外部模块处理
        # 这里只处理 Google 相关凭证

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

    def get_youtube_service(self):
        """获取 YouTube API 服务实例"""
        if self.youtube_service:
            return self.youtube_service

        self._log("=" * 50)
        self._log("[认证] 初始化 YouTube API...")
        self._log("=" * 50)

        creds = None

        if TOKEN_FILE.exists():
            self._log(f"[认证] 发现已有 token 文件")
            try:
                creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
            except Exception as e:
                self._log(f"[警告] Token 文件读取失败: {e}")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self._log("[认证] Token 已过期，正在刷新...")
                self._progress(55, "刷新认证 Token...")
                try:
                    config = load_config()
                    proxies = config.get('proxies', {})
                    http_request = Request()
                    if proxies.get('http') or proxies.get('https'):
                        import os
                        http_proxy = proxies.get('http') or proxies.get('https', '')
                        if http_proxy:
                            os.environ['http_proxy'] = http_proxy
                            os.environ['https_proxy'] = http_proxy
                            os.environ['HTTP_PROXY'] = http_proxy
                            os.environ['HTTPS_PROXY'] = http_proxy
                    creds.refresh(http_request)
                except Exception as e:
                    self._log(f"[错误] Token 刷新失败: {e}")
                    self._log("[提示] 请运行 'xhs2yt update --token' 重新授权")
                    raise AuthenticationError(f"Token 刷新失败: {e}")
            else:
                if not CREDENTIALS_FILE.exists():
                    error_msg = f"未找到 OAuth 凭证文件: {CREDENTIALS_FILE}"
                    self._log(f"[错误] {error_msg}")
                    raise FileNotFoundError(error_msg)

                self._log("[认证] 启动 OAuth 授权流程...")
                self._log("[认证] 浏览器将打开授权页面，请登录 Google 账号并授权")
                self._progress(55, "等待浏览器授权...")
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(CREDENTIALS_FILE), SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    self._log(f"[错误] OAuth 授权失败: {e}")
                    raise AuthorizationError(f"OAuth 授权失败: {e}")

            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            self._log(f"[认证] 凭证已保存到: {TOKEN_FILE}")

        try:
            self.youtube_service = build('youtube', 'v3', credentials=creds)
        except Exception as e:
            self._log(f"[错误] YouTube API 初始化失败: {e}")
            raise AuthenticationError(f"YouTube API 初始化失败: {e}")
        
        self._log("[认证] YouTube API 初始化成功!")

        return self.youtube_service

    def get_authorization_url(self) -> tuple:
        """获取 YouTube OAuth 授权 URL（用于 Web UI / MCP）"""
        self._log("=" * 50)
        self._log("[授权] 生成 YouTube OAuth 授权 URL...")
        self._log("=" * 50)

        if not CREDENTIALS_FILE.exists():
            error_msg = f"未找到 OAuth 凭证文件: {CREDENTIALS_FILE}\n请先从 Google Cloud Console 下载 credentials.json"
            self._log(f"[错误] {error_msg}")
            return False, error_msg

        try:
            with open(CREDENTIALS_FILE, 'r') as f:
                client_config = json.load(f)

            if 'installed' in client_config:
                client_config['installed']['redirect_uris'] = ['urn:ietf:wg:oauth:2.0:oob']
            elif 'web' in client_config:
                client_config['web']['redirect_uris'] = ['urn:ietf:wg:oauth:2.0:oob']

            self._flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            self._flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'

            auth_url, _ = self._flow.authorization_url(
                access_type='offline',
                prompt='consent'
            )

            session_data = {
                'client_config': client_config,
                'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                'scopes': SCOPES,
            }
            AUTH_SESSION_FILE.write_text(json.dumps(session_data, ensure_ascii=False, indent=2))

            self._log("[授权] 授权 URL 生成成功")
            self._log("[授权] 已保存授权会话，支持跨 MCP 调用完成授权")
            self._log("[授权] 请复制以下 URL 到浏览器完成授权:")
            self._log(auth_url)

            return True, auth_url

        except Exception as e:
            error_msg = f"生成授权 URL 失败: {str(e)}"
            self._log(f"[错误] {error_msg}")
            self._flow = None
            return False, error_msg

    def authorize_youtube_with_code(self, code: str) -> tuple:
        """使用授权码完成 YouTube OAuth 授权（支持跨进程 / MCP 调用）"""
        self._log("=" * 50)
        self._log("[授权] 使用授权码完成 YouTube OAuth 授权...")
        self._log("=" * 50)

        try:
            flow = self._flow

            if not flow:
                if not AUTH_SESSION_FILE.exists():
                    error_msg = "未找到授权会话，请先获取授权 URL"
                    self._log(f"[错误] {error_msg}")
                    return False, error_msg

                session_data = json.loads(AUTH_SESSION_FILE.read_text())
                client_config = session_data['client_config']
                redirect_uri = session_data.get('redirect_uri', 'urn:ietf:wg:oauth:2.0:oob')
                scopes = session_data.get('scopes', SCOPES)

                flow = InstalledAppFlow.from_client_config(client_config, scopes)
                flow.redirect_uri = redirect_uri

            flow.fetch_token(code=code)
            creds = flow.credentials

            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

            if AUTH_SESSION_FILE.exists():
                AUTH_SESSION_FILE.unlink()

            success_msg = f"授权成功！凭证已保存到: {TOKEN_FILE}"
            self._log(f"[授权] {success_msg}")

            self._flow = None
            return True, success_msg

        except Exception as e:
            error_msg = f"授权失败: {str(e)}"
            self._log(f"[错误] {error_msg}")
            return False, error_msg

    def authorize_youtube(self) -> tuple:
        """手动进行 YouTube OAuth 授权"""
        self._log("=" * 50)
        self._log("[授权] 开始 YouTube OAuth 授权流程...")
        self._log("=" * 50)

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
        
        Args:
            video_path: 视频文件路径
            title: 视频标题
            description: 视频描述
            tags: 标签列表
            category_id: 分类 ID
            privacy_status: 隐私设置
            
        Returns:
            包含 video_id, video_url, response 的字典
            
        Raises:
            QuotaExceededError: 上传配额超限
            VideoValidationError: 视频验证失败
            UploadError: 其他上传错误
        """
        self._log("=" * 50)
        self._log("[上传] 开始上传到 YouTube...")
        self._log("=" * 50)
        self._log(f"  - 标题: {title}")
        self._log(f"  - 隐私: {privacy_status}")
        self._progress(60, "准备上传...")

        try:
            youtube = self.get_youtube_service()
        except (AuthenticationError, AuthorizationError) as e:
            raise UploadError(f"认证失败: {e}")

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

        try:
            media = MediaFileUpload(
                video_path,
                chunksize=1024 * 1024,
                resumable=True,
                mimetype='video/*'
            )
        except FileNotFoundError:
            raise UploadError(f"视频文件不存在: {video_path}")
        except Exception as e:
            raise UploadError(f"视频文件读取失败: {e}")

        try:
            request = youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = 60 + status.progress() * 40
                    self._progress(progress, f"上传中... {int(status.progress() * 100)}%")

        except HttpError as e:
            error_content = str(e.content) if hasattr(e, 'content') else str(e)
            
            if e.resp.status == 403:
                if 'quotaExceeded' in error_content or 'uploadLimitExceeded' in error_content:
                    self._log("[错误] YouTube 上传配额已用完")
                    self._log("[提示] YouTube 每日上传配额有限，请明天再试")
                    raise QuotaExceededError("YouTube 上传配额已用完，请明天再试")
                elif 'forbidden' in error_content.lower():
                    self._log("[错误] 权限不足，无法上传视频")
                    raise UploadError("权限不足，无法上传视频")
                    
            elif e.resp.status == 400:
                if 'invalidCategoryId' in error_content:
                    self._log("[错误] 无效的视频分类 ID")
                    raise VideoValidationError(f"无效的视频分类 ID: {category_id}")
                elif 'invalidTags' in error_content:
                    self._log("[错误] 无效的视频标签")
                    raise VideoValidationError("无效的视频标签")
                else:
                    self._log(f"[错误] 视频验证失败: {e}")
                    raise VideoValidationError(f"视频验证失败: {e}")
                    
            elif e.resp.status == 413 or 'entityTooLarge' in error_content:
                self._log("[错误] 视频文件过大")
                raise VideoValidationError("视频文件过大，YouTube 限制最大 256GB")
                
            else:
                self._log(f"[错误] 上传失败 (HTTP {e.resp.status}): {e}")
                raise UploadError(f"上传失败: HTTP {e.resp.status}")
                
        except Exception as e:
            self._log(f"[错误] 上传过程发生异常: {e}")
            raise UploadError(f"上传失败: {e}")

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
