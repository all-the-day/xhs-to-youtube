# 小红书到 YouTube 视频搬运工具

## 项目概述

将小红书视频自动搬运到 YouTube 频道的 Python 命令行工具，支持：
- 自动下载小红书视频（无水印）
- OAuth 2.0 授权 YouTube 上传
- 自动去除视频水印
- 双语标题生成
- 批量获取用户视频列表（URL 带 xsec_token 确保可访问）

**版本**: 1.2.0

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
- `fetch_user_videos(user_url, output_file)` - 获取用户主页视频列表（URL 包含 xsec_token）

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
# 搬运单个视频（默认公开，自动去水印）
python main.py transfer "https://www.xiaohongshu.com/explore/xxx"

# 搬运视频并添加英文标题（生成双语标题）
python main.py transfer "小红书URL" --title-en "English Title"

# 自定义标签和隐私设置
python main.py transfer "小红书URL" --tags "vlog,life" --privacy unlisted

# 保留本地视频
python main.py transfer "小红书URL" --keep-video

# 获取用户主页所有视频链接（默认输出到 video_list.json）
python main.py fetch "https://www.xiaohongshu.com/user/profile/xxx"

# 获取用户视频并保存到指定文件
python main.py fetch "https://www.xiaohongshu.com/user/profile/xxx" --output my_videos.json
```

## 配置文件

### cookies.txt
小红书 Cookie 文件，Netscape 格式。使用浏览器扩展导出。

**导出方法：**
1. 登录小红书网站
2. 使用 Cookie Editor 等扩展导出 Cookie
3. 选择 JSON 格式导出
4. 转换为 Netscape 格式保存

**Netscape 格式示例：**
```
xiaohongshu.com	TRUE	/	FALSE	1802674392	a1	cookie_value
```

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

## Git 开发规范

### 分支管理策略

```
master        # 主分支，稳定版本（测试通过）
├── feature/xxx   # 功能分支（保留）
├── fix/xxx        # 修复分支（保留）
├── refactor/xxx   # 重构分支（保留）
└── docs/xxx       # 文档分支（保留）
```

### 当前分支

| 分支 | 说明 |
|------|------|
| master | 主分支 |
| feature/fetch-user-videos | 获取用户视频列表功能 |
| remove-gui | 移除 GUI 功能 |

### 分支命名规范

| 类型 | 命名 | 示例 |
|------|------|------|
| 功能 | `feature/功能名` | `feature/add-batch-upload` |
| 修复 | `fix/问题描述` | `fix/watermark-detection` |
| 重构 | `refactor/重构内容` | `refactor/remove-gui` |
| 文档 | `docs/文档内容` | `docs/update-readme` |

### 提交消息规范

格式：`类型: 简短描述`

| 类型 | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 代码重构 |
| `docs` | 文档更新 |
| `test` | 测试相关 |
| `chore` | 构建/工具变更 |

### 开发流程

1. **创建分支**
   ```bash
   git checkout master
   git pull
   git checkout -b feature/新功能名
   ```

2. **开发与提交**
   ```bash
   git add .
   git commit -m "feat: 添加XXX功能"
   ```

3. **回归测试（必须）**
   ```bash
   python test_flow.py
   ```

4. **合并回主分支**
   ```bash
   git checkout master
   git merge feature/新功能名
   # 功能分支保留，不删除
   ```

5. **清理上下文**
   ```
   执行 /clear 清理开发上下文，准备下一次开发
   ```

### 合并检查清单

- [ ] 代码已提交
- [ ] 回归测试通过 (`python test_flow.py`)
- [ ] 无遗留的调试代码
- [ ] 文档已更新（如需要）

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
1. 凭证状态检查（验证 YouTube API 连接，不上传视频）
2. 视频流选择（去水印）
3. 标题提取
4. 视频下载
5. 搬运流程准备检查（验证 API 连接和元数据生成，不上传视频）

**注意：** 测试不会实际上传视频到 YouTube，仅验证 API 认证和下载功能。当前 OAuth scope 仅有 `youtube.upload` 权限，如需读取频道信息需要添加 `youtube.readonly` 权限。

## .gitignore

敏感文件已配置忽略：
- `cookies.txt` - 小红书 Cookie
- `credentials.json` - Google OAuth 凭证
- `token.json` - OAuth Token
- `videos/` - 视频缓存
- `__pycache__/` - Python 缓存
- `venv/` - 虚拟环境
