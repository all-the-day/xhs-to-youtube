# 小红书到 YouTube 视频搬运工具

## 项目概述

将小红书视频自动搬运到 YouTube 频道的 Python 命令行工具，支持：
- 自动下载小红书视频（无水印）
- OAuth 2.0 授权 YouTube 上传
- 自动去除视频水印
- 双语标题生成

**版本**: 1.1.0

## 技术栈

- **Python 3.8+**
- **Google YouTube Data API v3** - 视频上传
- **OAuth 2.0** - Google 账号授权

## 项目结构

```
xhs-to-youtube/
├── __init__.py       # Python 包初始化
├── core.py           # 核心逻辑类 XHSToYouTube
├── main.py           # 命令行入口
├── test_flow.py      # 测试套件
├── setup.sh          # 环境配置脚本
├── .gitignore        # Git 忽略配置
├── cookies.txt       # 小红书 Cookie (需配置)
├── credentials.json  # Google OAuth 凭证 (需配置)
├── token.json        # OAuth Token (自动生成)
└── videos/           # 视频缓存目录
```

## 核心类

### XHSToYouTube (`core.py`)

主要方法：
- `download_video(url)` - 下载小红书视频（自动选择无水印版本）
- `_select_best_video_stream(page_text)` - 解析视频流并选择无水印版本
- `get_youtube_service()` - 获取 YouTube API 服务
- `authorize_youtube()` - OAuth 授权（本地服务器方式）
- `get_authorization_url()` - 获取授权 URL
- `authorize_youtube_with_code(code)` - 使用授权码完成授权
- `upload_to_youtube()` - 上传视频到 YouTube
- `transfer()` - 完整搬运流程

### 凭证状态类

```python
@dataclass
class CredentialStatus:
    name: str      # 凭证名称
    exists: bool   # 文件是否存在
    valid: bool    # 是否有效
    message: str   # 状态消息
    path: str      # 文件路径
```

## 去水印功能

### 实现原理

小红书视频流有两种格式：
- **h264 格式**：`streamDesc` 以 `WM_` 开头（Watermark），带水印
- **h265 格式**：`streamDesc` 不含 `WM` 前缀，无水印

### 选择逻辑

1. 解析页面中的 h264 和 h265 视频流
2. 根据 `streamDesc` 字段判断是否含水印
3. 优先选择无水印的 h265 流
4. 如果没有无水印版本，回退到 h264 流

### 示例

```
h264: WM_X264_MP4_web      → 有水印
h265: X265_MP4_WEB_114     → 无水印 ✓
```

## 运行命令

### 环境配置

```bash
# 安装依赖
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 requests

# 或运行配置脚本
bash setup.sh
```

### 命令行使用

```bash
# 基本用法（默认公开，自动去水印）
python main.py "https://www.xiaohongshu.com/explore/xxx"

# 添加英文标题（生成双语标题）
python main.py "小红书URL" --title-en "English Title"

# 自定义标签和隐私设置
python main.py "小红书URL" --tags "vlog,life" --privacy unlisted

# 保留本地视频
python main.py "小红书URL" --keep-video
```

## 配置文件

### cookies.txt
小红书 Cookie 文件，Netscape 格式。使用浏览器扩展（如 EditThisCookie）导出。

### credentials.json
Google Cloud Console 下载的 OAuth 2.0 客户端凭证：
1. 创建 Google Cloud 项目
2. 启用 YouTube Data API v3
3. 配置 OAuth 同意屏幕（外部用户）
4. 创建 OAuth 客户端 ID（桌面应用）
5. 下载 JSON 文件

### token.json
OAuth 授权后自动生成，存储访问令牌。

## OAuth 授权流程

首次运行时，脚本会自动打开浏览器进行授权，授权成功后自动生成 `token.json`。

## 视频元数据

### 标题
- 默认使用原视频标题
- 可选添加英文标题，生成双语格式：`【原标题】English Title`

### 描述
- 原视频描述（如有）
- 标注"原创"

### 隐私设置
- 默认：公开 (public)
- 可选：不公开 (unlisted)、私享 (private)

## 开发约定

- 使用 `log_callback` 和 `progress_callback` 进行日志和进度回调
- 进度值范围：0-100
- 错误处理：返回 `(success: bool, message: str)` 元组
- 编码：UTF-8

## 依赖版本

```
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
requests
```

## 测试

```bash
# 运行测试套件
python test_flow.py
```

测试内容包括：
1. 凭证状态检查
2. 视频流选择（去水印）
3. 标题提取
4. 视频下载
5. 完整搬运流程

## .gitignore

敏感文件已配置忽略：
- `cookies.txt` - 小红书 Cookie
- `credentials.json` - Google OAuth 凭证
- `token.json` - OAuth Token
- `videos/` - 视频缓存
- `__pycache__/` - Python 缓存
- `venv/` - 虚拟环境