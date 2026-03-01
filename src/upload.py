"""
YouTube 上传模块
处理 OAuth 认证和视频上传
"""

import json
import sys
from pathlib import Path
from typing import Callable, Optional

from src.config import CREDENTIALS_FILE, TOKEN_FILE, SCOPES
from src.models import CredentialStatus

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
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self._log("[认证] Token 已过期，正在刷新...")
                self._progress(55, "刷新认证 Token...")
                creds.refresh(Request())
            else:
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

            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            self._log(f"[认证] 凭证已保存到: {TOKEN_FILE}")

        self.youtube_service = build('youtube', 'v3', credentials=creds)
        self._log("[认证] YouTube API 初始化成功!")

        return self.youtube_service

    def get_authorization_url(self) -> tuple:
        """获取 YouTube OAuth 授权 URL（用于 Web UI）"""
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
        """使用授权码完成 YouTube OAuth 授权"""
        self._log("=" * 50)
        self._log("[授权] 使用授权码完成 YouTube OAuth 授权...")
        self._log("=" * 50)

        if not self._flow:
            error_msg = "未找到授权会话，请先获取授权 URL"
            self._log(f"[错误] {error_msg}")
            return False, error_msg

        try:
            self._flow.fetch_token(code=code)
            creds = self._flow.credentials

            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

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
        """上传视频到 YouTube"""
        self._log("=" * 50)
        self._log("[上传] 开始上传到 YouTube...")
        self._log("=" * 50)
        self._log(f"  - 标题: {title}")
        self._log(f"  - 隐私: {privacy_status}")
        self._progress(60, "准备上传...")

        youtube = self.get_youtube_service()

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

        media = MediaFileUpload(
            video_path,
            chunksize=1024 * 1024,
            resumable=True,
            mimetype='video/*'
        )

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
