#!/usr/bin/env python3
"""
小红书到 YouTube 视频搬运工具 - Web GUI
使用 Gradio 构建

启动方法:
    python gui.py
    或
    python gui.py --share  # 生成公网分享链接
"""

import argparse
import os
import threading
import time
from pathlib import Path

# 清除代理环境变量，避免 httpx socks 代理兼容问题
for proxy_var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 
                  'all_proxy', 'ALL_PROXY', 'no_proxy', 'NO_PROXY']:
    os.environ.pop(proxy_var, None)

try:
    import gradio as gr
except ImportError:
    print("请先安装 Gradio:")
    print("pip install gradio")
    exit(1)

from core import XHSToYouTube, CredentialStatus, COOKIES_FILE, CREDENTIALS_FILE, TOKEN_FILE

# GUI 状态
class GUIState:
    def __init__(self):
        self.logs = []
        self.progress_value = 0
        self.progress_status = ""
    
    def reset(self):
        self.logs = []
        self.progress_value = 0
        self.progress_status = ""

state = GUIState()


def log_callback(message: str):
    """日志回调"""
    timestamp = time.strftime("%H:%M:%S")
    state.logs.append(f"[{timestamp}] {message}")


def progress_callback(value: float, status: str):
    """进度回调"""
    state.progress_value = value / 100.0  # Gradio 使用 0-1 范围
    state.progress_status = status


def check_credentials_before_transfer():
    """检查搬运前的凭证状态，返回 (是否有效, 错误消息)"""
    errors = []
    
    # 检查 Cookie
    if not COOKIES_FILE.exists():
        errors.append("❌ 小红书 Cookie 文件不存在 (cookies.txt)")
    else:
        content = COOKIES_FILE.read_text().strip()
        if not content or content.startswith('{'):
            errors.append("❌ 小红书 Cookie 文件格式错误，请导出 Netscape 格式")
    
    # 检查 Google 凭证
    if not CREDENTIALS_FILE.exists():
        errors.append("❌ Google OAuth 凭证不存在 (credentials.json)")
    
    # 检查 Token（YouTube 授权）
    if not TOKEN_FILE.exists():
        errors.append("❌ YouTube 未授权，请先完成 OAuth 授权")
    
    if errors:
        return False, "\n".join(errors)
    return True, ""


def transfer_video(
    url: str,
    english_title: str,
    tags: str,
    privacy: str,
    keep_video: bool,
    progress=gr.Progress()
):
    """
    执行视频搬运
    """
    state.reset()
    
    # 检查 URL
    if not url or not url.strip():
        yield "请输入小红书视频 URL", "", gr.update(value=""), progress(0, desc="等待输入...")
        return
    
    # 检查凭证状态
    valid, error_msg = check_credentials_before_transfer()
    if not valid:
        yield f"凭证检查失败:\n{error_msg}", "", gr.update(value=""), progress(0, desc="凭证缺失")
        return
    
    # 处理标签
    tag_list = None
    if tags and tags.strip():
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    # 创建传输工具实例
    tool = XHSToYouTube(
        log_callback=log_callback,
        progress_callback=progress_callback
    )
    
    # 启动传输线程
    result_container = {'result': None, 'error': None}
    
    def run_transfer():
        try:
            result_container['result'] = tool.transfer(
                xhs_url=url.strip(),
                english_title=english_title.strip() if english_title else None,
                custom_desc=None,
                tags=tag_list,
                privacy=privacy,
                keep_video=keep_video
            )
        except Exception as e:
            result_container['error'] = str(e)
    
    thread = threading.Thread(target=run_transfer)
    thread.start()
    
    # 更新 UI
    last_log_count = 0
    while thread.is_alive():
        thread.join(timeout=0.1)
        
        # 更新进度
        progress(state.progress_value, desc=state.progress_status)
        
        # 更新日志
        if len(state.logs) > last_log_count:
            log_text = "\n".join(state.logs)
            yield "处理中...", log_text, gr.update(value=""), progress(state.progress_value, desc=state.progress_status)
            last_log_count = len(state.logs)
    
    # 最终结果
    log_text = "\n".join(state.logs)
    
    if result_container['error']:
        yield f"错误: {result_container['error']}", log_text, gr.update(value=""), progress(1, desc="失败")
    elif result_container['result']:
        result = result_container['result']
        yield "搬运完成!", log_text, gr.update(value=result['video_url'])
    else:
        yield "未知错误", log_text, gr.update(value=""), progress(1, desc="失败")


def check_credentials():
    """检查凭证状态"""
    tool = XHSToYouTube()
    statuses = tool.check_credentials()
    
    results = []
    for key, status in statuses.items():
        icon = "✅" if status.valid else ("⚠️" if status.exists else "❌")
        results.append(f"{icon} **{status.name}**: {status.message}")
        results.append(f"   路径: `{status.path}`")
        results.append("")
    
    return "\n".join(results)


def authorize_youtube():
    """
    手动进行 YouTube OAuth 授权（命令行方式，使用本地服务器）
    返回 (credential_status, authorize_result)
    """
    tool = XHSToYouTube()
    success, message = tool.authorize_youtube()
    
    # 刷新凭证状态
    new_status = check_credentials()
    
    if success:
        return new_status, f"✅ {message}"
    else:
        return new_status, f"❌ {message}"


# 全局变量存储 flow 对象（用于 Web UI 授权）
_auth_flow = None


def get_auth_url():
    """
    获取 YouTube OAuth 授权 URL（用于 Web UI）
    返回 (credential_status, auth_url_display, auth_code_input, status_message)
    """
    global _auth_flow
    
    tool = XHSToYouTube()
    success, url_or_msg = tool.get_authorization_url()
    
    if success:
        _auth_flow = tool._flow  # 保存 flow 对象
        return (
            check_credentials(),
            url_or_msg,
            "",  # 清空授权码输入框
            "✅ 请复制上方 URL 到浏览器完成授权，然后将授权码粘贴到下方输入框"
        )
    else:
        return (
            check_credentials(),
            "",
            "",
            f"❌ {url_or_msg}"
        )


def submit_auth_code(auth_code: str):
    """
    使用授权码完成 YouTube OAuth 授权（用于 Web UI）
    返回 (credential_status, auth_url_display, auth_code_input, status_message)
    """
    global _auth_flow
    
    if not auth_code or not auth_code.strip():
        return (
            check_credentials(),
            "",
            "",
            "❌ 请输入授权码"
        )
    
    if not _auth_flow:
        return (
            check_credentials(),
            "",
            "",
            "❌ 授权会话已过期，请重新获取授权 URL"
        )
    
    tool = XHSToYouTube()
    tool._flow = _auth_flow  # 恢复 flow 对象
    
    success, message = tool.authorize_youtube_with_code(auth_code.strip())
    
    if success:
        _auth_flow = None  # 清理全局 flow
        return (
            check_credentials(),
            "",
            "",
            f"✅ {message}"
        )
    else:
        return (
            check_credentials(),
            "",
            auth_code,  # 保留用户输入
            f"❌ {message}"
        )


def reset_form():
    """重置表单到初始状态"""
    state.reset()
    return (
        "",  # url_input
        "",  # title_en_input
        "",  # tags_input
        "public",  # privacy_dropdown
        False,  # keep_video_checkbox
        "",  # status_output
        "",  # video_url_output
        ""  # log_output
    )


def create_ui():
    """创建 Gradio 界面"""
    
    # 自定义 CSS
    custom_css = """
    .gradio-container {
        max-width: 900px !important;
    }
    .status-box {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 20px;
        color: #eee;
    }
    .log-box textarea {
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-size: 12px;
        background: #1e1e1e !important;
        color: #d4d4d4 !important;
    }
    footer {
        display: none !important;
    }
    """
    
    with gr.Blocks(
        title="小红书 → YouTube 视频搬运工具"
    ) as app:
        
        gr.Markdown(
            """
            # 🎬 小红书 → YouTube 视频搬运工具
            
            轻松将小红书视频搬运到你的 YouTube 频道，支持双语标题和进度追踪。
            """
        )
        
        with gr.Tabs():
            # Tab 1: 视频搬运
            with gr.TabItem("📤 视频搬运"):
                with gr.Row():
                    with gr.Column(scale=3):
                        url_input = gr.Textbox(
                            label="小红书视频 URL",
                            placeholder="https://www.xiaohongshu.com/explore/...",
                            lines=1
                        )
                
                with gr.Row():
                    with gr.Column(scale=2):
                        title_en_input = gr.Textbox(
                            label="英文标题（可选）",
                            placeholder="输入英文标题，将生成双语标题",
                            lines=1
                        )
                    with gr.Column(scale=1):
                        tags_input = gr.Textbox(
                            label="标签（可选）",
                            placeholder="用逗号分隔，如: vlog,life,daily",
                            lines=1
                        )
                
                with gr.Row():
                    with gr.Column(scale=1):
                        privacy_dropdown = gr.Dropdown(
                            label="隐私设置",
                            choices=[
                                ("公开 (public)", "public"),
                                ("不公开 (unlisted)", "unlisted"),
                                ("私享 (private)", "private")
                            ],
                            value="public"
                        )
                    with gr.Column(scale=1):
                        keep_video_checkbox = gr.Checkbox(
                            label="保留本地视频文件",
                            value=False
                        )
                
                with gr.Row():
                    submit_btn = gr.Button(
                        "🚀 开始搬运",
                        variant="primary",
                        size="lg"
                    )
                    reset_btn = gr.Button(
                        "🔄 重置",
                        variant="secondary",
                        size="lg"
                    )
                
                with gr.Row():
                    with gr.Column():
                        status_output = gr.Textbox(
                            label="状态",
                            interactive=False,
                            lines=1
                        )
                        video_url_output = gr.Textbox(
                            label="视频链接",
                            interactive=False,
                            lines=1
                        )
                
                log_output = gr.Textbox(
                    label="操作日志",
                    interactive=False,
                    lines=10,
                    max_lines=20,
                    elem_classes=["log-box"]
                )
                
                # 绑定事件
                submit_btn.click(
                    fn=transfer_video,
                    inputs=[
                        url_input,
                        title_en_input,
                        tags_input,
                        privacy_dropdown,
                        keep_video_checkbox
                    ],
                    outputs=[
                        status_output,
                        log_output,
                        video_url_output
                    ]
                )
                
                # 重置按钮事件
                reset_btn.click(
                    fn=reset_form,
                    outputs=[
                        url_input,
                        title_en_input,
                        tags_input,
                        privacy_dropdown,
                        keep_video_checkbox,
                        status_output,
                        video_url_output,
                        log_output
                    ]
                )
            
            # Tab 2: 凭证管理
            with gr.TabItem("🔑 凭证管理"):
                gr.Markdown("### 凭证状态检查")
                
                credential_status = gr.Markdown(
                    value="点击下方按钮检查凭证状态",
                    elem_classes=["status-box"]
                )
                
                with gr.Row():
                    refresh_btn = gr.Button("🔄 刷新状态", variant="secondary")
                
                gr.Markdown("---")
                gr.Markdown("### YouTube OAuth 授权")
                gr.Markdown("**方式一：Web UI 授权（推荐）**")
                
                with gr.Row():
                    get_auth_url_btn = gr.Button("🔗 获取授权 URL", variant="primary")
                
                auth_url_display = gr.Textbox(
                    label="授权 URL（复制到浏览器打开）",
                    interactive=False,
                    lines=2
                )
                
                auth_code_input = gr.Textbox(
                    label="授权码（从浏览器获取后粘贴到这里）",
                    placeholder="粘贴授权码...",
                    lines=1
                )
                
                submit_auth_code_btn = gr.Button("✅ 完成授权", variant="primary")
                
                auth_status = gr.Textbox(
                    label="授权状态",
                    interactive=False,
                    lines=2
                )
                
                gr.Markdown("---")
                gr.Markdown("**方式二：命令行授权（需要终端访问）**")
                
                authorize_btn = gr.Button("🔐 授权 YouTube（本地服务器方式）", variant="secondary")
                
                authorize_result = gr.Textbox(
                    label="授权结果",
                    interactive=False,
                    lines=2
                )
                
                # 绑定事件
                refresh_btn.click(
                    fn=check_credentials,
                    outputs=credential_status
                )
                
                # Web UI 授权方式
                get_auth_url_btn.click(
                    fn=get_auth_url,
                    outputs=[credential_status, auth_url_display, auth_code_input, auth_status]
                )
                
                submit_auth_code_btn.click(
                    fn=submit_auth_code,
                    inputs=auth_code_input,
                    outputs=[credential_status, auth_url_display, auth_code_input, auth_status]
                )
                
                # 命令行授权方式
                authorize_btn.click(
                    fn=authorize_youtube,
                    outputs=[credential_status, authorize_result]
                )
                
                gr.Markdown(
                    """
                    ---
                    
                    ### 📋 配置指南
                    
                    #### 1. 小红书 Cookie
                    1. 安装 Chrome 扩展 `EditThisCookie` 或 `Cookie Editor`
                    2. 登录 [小红书网页版](https://www.xiaohongshu.com)
                    3. 点击扩展图标，导出 Cookie 为 Netscape 格式
                    4. 保存到: `cookies.txt`
                    
                    #### 2. Google OAuth 凭证
                    1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
                    2. 创建项目 → 启用 **YouTube Data API v3**
                    3. 配置 OAuth 同意屏幕（选"外部"，添加自己邮箱为测试用户）
                    4. 创建 OAuth 客户端 ID（桌面应用）
                    5. 下载 JSON 并保存为: `credentials.json`
                    
                    #### 3. YouTube Token
                    首次使用时，脚本会自动打开浏览器进行授权，授权成功后会自动生成 `token.json`
                    """
                )
        
        # 页面加载时检查凭证
        app.load(
            fn=check_credentials,
            outputs=credential_status
        )
    
    return app


def main():
    parser = argparse.ArgumentParser(description="小红书到 YouTube 视频搬运工具 - Web GUI")
    parser.add_argument("--share", action="store_true", help="生成公网分享链接")
    parser.add_argument("--port", type=int, default=7860, help="端口号 (默认: 7860)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="主机地址 (默认: 127.0.0.1)")
    args = parser.parse_args()
    
    print(f"\n{'='*50}")
    print("小红书 → YouTube 视频搬运工具")
    print(f"{'='*50}")
    print(f"\n启动 Web UI...")
    print(f"地址: http://{args.host}:{args.port}")
    if args.share:
        print("公网分享链接: 将在启动后显示")
    print("\n按 Ctrl+C 退出\n")
    
    app = create_ui()
    app.launch(
        share=args.share,
        server_name=args.host,
        server_port=args.port
    )


if __name__ == "__main__":
    main()
