# 小红书到 YouTube 视频搬运工具

## 项目概述

将小红书视频自动搬运到 YouTube 频道的 Python 命令行工具，支持：
- 自动下载小红书视频（无水印）
- OAuth 2.0 授权 YouTube 上传
- 自动去除视频水印
- AI 翻译标题和描述（支持 DeepLX、MyMemory、DeepL、OpenAI）
- 批量获取用户视频列表（URL 带 xsec_token 确保可访问）
- 批量上传视频列表（随机间隔、自动跳过已上传、数量限制）
- **智能受众分析**（地理位置 + 年龄/性别 → 最佳发布时间 + 内容建议）
- **发布时间智能确认**（非推荐时段询问是否继续）
- 每日上传限制检测（默认 10 个/天）
- **邮件推送功能**（可选，发送技术日报到邮箱）

**版本**: 1.5.0

## 技术栈

- **Python 3.10+**
- **Google YouTube Data API v3** - 视频上传
- **OAuth 2.0** - Google 账号授权
- **OpenAI API** - 可选，AI 翻译
- **SMTP** - 可选，邮件推送

## 项目结构

```
xhs-to-youtube/
├── main.py              # 兼容入口（包装器）
├── pyproject.toml       # 项目配置
├── src/
│   ├── __init__.py      # Python 包初始化
│   ├── cli.py           # CLI 入口（子命令：transfer/fetch/batch/update/status/analyze）
│   ├── core.py          # 核心逻辑类 XHSToYouTube
│   ├── config.py        # 配置常量
│   ├── models.py        # 数据类定义
│   ├── download.py      # 视频下载模块
│   ├── upload.py        # YouTube 上传模块
│   ├── fetch.py         # 用户视频列表获取模块
│   ├── translate.py     # 翻译服务模块
│   ├── analyze.py       # 受众分析模块（地理位置、年龄、性别、时间推荐）
│   └── interactive.py   # 交互式命令行界面
├── scripts/
│   ├── send_digest_email.py   # 邮件推送脚本
│   ├── setup_email.sh         # 邮件配置脚本
│   ├── email_config.example.sh # 邮件配置模板
│   └── README_EMAIL.md        # 邮件功能文档
├── tests/
│   ├── __init__.py
│   └── test_flow.py     # 测试套件
├── config/
│   └── config.example.json  # 翻译服务配置示例
├── cache/
│   └── videos/          # 视频缓存目录
├── data/
│   ├── video_list.json        # fetch 输出文件
│   ├── uploaded.json          # 已上传记录
│   ├── timezone_cache.json    # 受众分析缓存
│   └── 地理位置.../表格数据.csv   # YouTube Studio 导出的受众数据
├── cookies.txt          # 小红书 Cookie (需配置)
├── credentials.json     # Google OAuth 凭证 (需配置)
└── token.json           # OAuth Token (自动生成)
```

## 核心模块

### XHSToYouTube (`src/core.py`)

核心协调类，整合各子模块功能。

**主要方法：**
| 方法 | 说明 |
|------|------|
| `transfer(xhs_url, ...)` | 完整搬运流程（下载 → 翻译 → 上传 + 时间建议确认） |
| `batch_transfer(video_list_path, ...)` | 批量搬运视频列表（支持数量限制） |
| `fetch_user_videos(user_url, ...)` | 获取用户主页视频列表 |
| `download_video(url, ...)` | 下载小红书视频 |
| `upload_to_youtube(...)` | 上传视频到 YouTube |
| `translate(text, target_type)` | 翻译文本 |
| `check_credentials()` | 检查凭证状态 |
| `update_cookie(content)` | 更新小红书 Cookie |
| `check_upload_limit()` | 检查每日上传限制 |
| `get_authorization_url()` | 获取 OAuth 授权 URL |
| `authorize_youtube_with_code(code)` | 使用授权码完成授权 |
| `_show_time_suggestion()` | 显示发布时间建议 |
| `_get_time_slot_info(hour)` | 获取上传时间段标签 |

### AudienceAnalyzer (`src/analyze.py`)

受众分析模块，基于 YouTube Studio 导出的数据：
- 解析地理位置 CSV（观看者地区分布）
- 解析年龄/性别 CSV（人口统计 + 交叉分析）
- 智能计算最佳发布时间（结合受众年龄、地区工作文化）
- 生成受众画像（年龄段、性别比例、内容建议）

**核心函数：**
| 函数 | 说明 |
|------|------|
| `analyze_and_cache(force, log_callback)` | 执行分析并缓存结果 |
| `get_time_recommendation()` | 获取时间推荐（支持缓存） |
| `is_good_upload_time(hour)` | 检查当前是否在推荐时段 |
| `format_audience_report(cache, hour)` | 格式化完整报告 |
| `format_time_suggestion(rec, hour)` | 格式化时间建议提示 |
| `calculate_best_upload_time(regions, demographics)` | 智能计算发布时间 |

### VideoDownloader (`src/download.py`)

视频下载模块，处理：
- 小红书视频页面解析
- 无水印视频流选择（h265 优先）
- 视频文件下载

### YouTubeUploader (`src/upload.py`)

YouTube 上传模块，处理：
- OAuth 2.0 认证流程
- 视频上传（支持断点续传）
- 凭证状态检查

### VideoFetcher (`src/fetch.py`)

用户视频列表获取模块，支持三种方式：
1. **API 方式**（优先）- 直接调用小红书 API
2. **页面解析**（回退）- 解析页面 HTML
3. **Playwright**（备选）- 通过远程浏览器获取

### TranslateService (`src/translate.py`)

翻译服务模块，支持多种 API：

| 服务 | 配置字段 | 说明 |
|------|----------|------|
| DeepLX | `deeplx_url` | 免费，需本地部署 |
| MyMemory | 无需配置 | 免费，5000 字符/天限额 |
| DeepL | `deepl_api_key` | 官方 API |
| OpenAI | `openai_api_key` | GPT 翻译 |

**翻译优先级：** DeepLX → MyMemory → DeepL → OpenAI

## 运行命令

### 安装

```bash
# 使用 pip 安装
pip install -e .

# 安装后可使用简短命令
xhs2yt -i

# 或直接运行模块
python -m src.cli -i

# 可选：翻译功能
pip install openai

# 可选：Playwright 方式获取视频列表
pip install playwright && playwright install chromium
```

### 命令行使用

```bash
# 交互式模式（推荐新手）
python -m src.cli -i
# 或安装后使用
xhs2yt -i

# 搬运单个视频（默认公开，自动去水印）
python -m src.cli transfer "https://www.xiaohongshu.com/explore/xxx"

# 搬运视频 + AI 翻译
python -m src.cli transfer "小红书URL" --translate

# 搬运视频 + 手动指定英文标题
python -m src.cli transfer "小红书URL" --title-en "English Title"

# 自定义标签和隐私设置
python -m src.cli transfer "小红书URL" --tags "vlog,life" --privacy unlisted

# 保留本地视频
python -m src.cli transfer "小红书URL" --keep-video

# 获取用户主页所有视频链接（默认输出到 data/video_list.json）
python -m src.cli fetch "https://www.xiaohongshu.com/user/profile/xxx"

# 获取用户视频，每页20条
python -m src.cli fetch "用户主页URL" --page-size 20 -o my_videos.json

# 批量上传视频列表（默认开启翻译）
python -m src.cli batch

# 批量上传 + 禁用翻译
python -m src.cli batch --no-translate

# 批量上传指定文件，自定义间隔时间
python -m src.cli batch --input my_videos.json --interval-min 15 --interval-max 45

# 批量上传，限制上传数量（新增）
python -m src.cli batch --limit 5

# 强制重新上传所有视频（不跳过已上传）
python -m src.cli batch --force

# 分析受众数据，推荐最佳发布时间
python -m src.cli analyze

# 强制重新分析（忽略缓存）+ 详细输出
python -m src.cli analyze --force --verbose

# 更新所有凭证（Cookie + Token）
python -m src.cli update

# 只更新 Cookie
python -m src.cli update --cookie

# 只更新 Token
python -m src.cli update --token

# 查看凭证状态
python -m src.cli status
```

## 受众分析功能

### 数据来源

从 YouTube Studio 导出受众数据：
1. **地理位置**：受众 → 地理位置 → 导出 CSV
2. **年龄/性别**：受众 → 年龄/性别 → 导出 CSV

将导出的 CSV 文件放到 `data/` 目录下，文件名需包含 `地理位置` 或 `年龄`/`性别` 关键字。

### 智能分析维度

**地理位置分析：**
- 解析观看者地区分布
- 计算主要受众时区权重
- 支持全球主要国家的时区映射

**年龄/性别分析：**
- 年龄段观看量/时长占比
- 性别分布比例
- 年龄×性别交叉分析（细粒度洞察）

**智能时间推荐：**
- 结合地区工作文化（下班时间、晚餐习惯）
- 结合年龄作息规律（学生/上班族/退休）
- 自动时区转换（受众时区 → 用户时区）

### 地区工作文化特征

| 地区 | 下班时间 | 黄金时段 |
|------|----------|----------|
| 大陆/香港 | 18:00 | 20:00-23:00 |
| 台湾 | 18:00 | 19:00-23:00 |
| 日本 | 19:00 | 21:00-24:00 |
| 欧美 | 17:00 | 19:00-23:00 |

### 年龄作息规律

| 年龄段 | 类型 | 活跃时段 |
|--------|------|----------|
| 13-17岁 | 学生 | 16:00-22:00 |
| 18-24岁 | 年轻学生 | 18:00-24:00 |
| 25-44岁 | 上班族 | 20:00-23:00 |
| 65岁+ | 退休 | 10:00-12:00 |

### 分析输出示例

```
📊 受众画像分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌍 地理位置分布 (Top 5):
  1. TW: 45.2% [UTC+8]
  2. HK: 22.1% [UTC+8]
  3. CN: 15.3% [UTC+8]
  4. JP: 8.5% [UTC+9]
  5. US: 3.2% [UTC-5]

👥 年龄分布:
  25-34 岁: 38% ███████░░░░░░░░░░░░░
  18-24 岁: 25% █████░░░░░░░░░░░░░░░
  35-44 岁: 20% ████░░░░░░░░░░░░░░░░

👤 性别分布:
  女: 62% ████████░░░░░░░░░░░░
  男: 38% █████░░░░░░░░░░░░░░░

⏰ 发布时间建议:
  当前时间: 21:00 (北京时间)
  ✅ 当前处于黄金时段！
  🎯 黄金时段: 20:00-23:00 (建议)
  📊 次选时段: 12:00-13:00

💡 受众洞察:
  主要年龄: 25-34 岁 (38%)
  性别比例: 男38% 女62%
  内容建议: 职场/生活、细腻情感、繁体字幕
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 发布时间智能确认

单视频搬运时，系统会根据受众分析结果智能提示：

```
⏰  发布时间建议
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  当前时间: 14:00 (北京时间)
  
  ⚠️  当前不在推荐时段
  
  🎯 黄金时段: 20:00-23:00 (建议)
  📊 次选时段: 12:00-13:00
  
  受众: 上班族，地区: TW(45%), HK(22%), CN(15%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

是否继续上传? [y/N]: 
```

- 黄金时段/次选时段：自动继续上传
- 非推荐时段：询问用户确认

## 邮件推送功能

可选功能，发送技术日报到邮箱（支持推送到手机）。

### 快速配置

```bash
# 1. 复制配置模板
cd ~/xhs-to-youtube/scripts
cp email_config.example.sh email_config.sh

# 2. 编辑配置（填入邮箱和应用密码）
vim email_config.sh

# 3. 测试发送
source email_config.sh && python3 send_digest_email.py
```

### Gmail 配置

1. 开启两步验证：https://myaccount.google.com/security
2. 生成应用专用密码：https://myaccount.google.com/apppasswords
3. 复制 16 位密码（无空格）到配置文件

### 自动发送

```bash
# 添加到 crontab（每天早上 8 点）
crontab -e

# 添加行：
0 8 * * * source /home/duoban/xhs-to-youtube/scripts/email_config.sh && python3 /home/duoban/xhs-to-youtube/scripts/send_digest_email.py >> ~/digest/logs/email.log 2>&1
```

详细配置见 `scripts/README_EMAIL.md`。

## 配置文件

### cookies.txt

小红书 Cookie 文件，支持 **JSON** 和 **Netscape** 两种格式。

**导出方法：**
1. 登录小红书网站
2. 使用 Cookie Editor 等扩展导出 Cookie
3. 选择 JSON 格式导出，直接粘贴即可（脚本自动转换）

### credentials.json

Google Cloud Console 下载的 OAuth 2.0 客户端凭证：
1. 创建 Google Cloud 项目
2. 启用 YouTube Data API v3
3. 配置 OAuth 同意屏幕（外部用户）
4. 创建 OAuth 客户端 ID（桌面应用）
5. 下载 JSON 文件

### token.json

OAuth 授权后自动生成，存储访问令牌。

### config/config.json（可选）

翻译服务配置，参考 `config/config.example.json`：

```json
{
  "deeplx_url": "http://localhost:1188",
  "proxies": {},
  "deepl_api_key": "",
  "deepl_free": true,
  "openai_api_key": "",
  "openai_base_url": "https://api.openai.com/v1",
  "openai_model": "gpt-4o-mini"
}
```

## 数据结构

### fetch_user_videos 返回结构

```json
{
  "user_id": "用户ID",
  "fetch_time": "2026-02-16 09:27:07",
  "total_count": 4,
  "videos": [
    {
      "note_id": "笔记ID",
      "title": "视频标题",
      "url": "https://www.xiaohongshu.com/explore/xxx?xsec_token=xxx",
      "xsec_token": "访问令牌",
      "desc": "视频描述"
    }
  ]
}
```

### batch_transfer 返回结构

```json
{
  "success": true,
  "total": 10,
  "skipped": 2,
  "success_count": 7,
  "failed": 1,
  "failed_videos": [
    {
      "note_id": "xxx",
      "title": "失败的视频标题",
      "error": "错误信息"
    }
  ]
}
```

### 上传记录结构 (uploaded.json)

```json
{
  "records": {
    "note_id": {
      "youtube_id": "shaLodkyKS4",
      "youtube_url": "https://www.youtube.com/watch?v=shaLodkyKS4",
      "title": "翻译后的英文标题",
      "uploaded_at": "2026-03-04 19:09:33",
      "upload_hour": 19,
      "time_slot": "黄金时段",
      "recommendation_followed": true
    }
  }
}
```

### 数据类

```python
@dataclass
class CredentialStatus:
    name: str      # 凭证名称
    exists: bool   # 文件是否存在
    valid: bool    # 是否有效
    message: str   # 状态消息
    path: str      # 文件路径

@dataclass
class UploadRecord:
    note_id: str           # 小红书笔记 ID
    youtube_id: str        # YouTube 视频 ID
    youtube_url: str       # YouTube 视频链接
    title: str             # 视频标题（翻译后）
    uploaded_at: str       # 上传时间
    upload_hour: int       # 上传小时 (0-23)
    time_slot: str         # 时间段标签
    recommendation_followed: bool  # 是否遵循推荐时段

@dataclass
class AudienceRegion:
    code: str        # 国家代码 (e.g., "TW", "JP")
    views: int       # 观看次数
    weight: float    # 权重占比 (0-1)
    timezone: str    # 时区偏移 (e.g., "UTC+8")

@dataclass
class AgeGroup:
    age_range: str          # 年龄段
    views_percent: float    # 观看次数占比
    watch_time_percent: float  # 观看时长占比

@dataclass
class GenderData:
    gender: str             # 性别
    views_percent: float    # 观看次数占比
    watch_time_percent: float  # 观看时长占比

@dataclass
class DemographicsData:
    age_groups: list[AgeGroup]       # 年龄分组
    genders: list[GenderData]        # 性别分布
    age_gender_breakdown: list[dict] # 年龄×性别交叉数据

@dataclass
class TimeRecommendation:
    optimal_time: str         # 最佳发布时间段
    secondary_time: str       # 次选时间段
    user_timezone: str        # 用户所在时区
    primary_tz_weight: float  # 主要时区权重占比
    reason: str               # 推荐原因

@dataclass
class AudienceInsight:
    primary_age_group: str    # 主要年龄段
    primary_age_percent: float
    gender_ratio: str         # 性别比例
    dominant_gender: str      # 主导性别
    content_suggestion: str   # 内容风格建议

@dataclass
class AudienceCache:
    geo_source_file: str      # 地理位置数据源
    geo_source_md5: str       # 文件哈希（变化检测）
    demo_source_file: str     # 人口统计数据源
    analyzed_at: str          # 分析时间
    regions: list[AudienceRegion]
    demographics: DemographicsData
    recommendation: TimeRecommendation
    insight: AudienceInsight
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

## 每日上传限制

默认限制每日上传 10 个视频，可在 `src/config.py` 中修改 `DAILY_UPLOAD_LIMIT`。

达到限制时：
- 批量上传自动停止
- 显示剩余配额提示
- 建议第二天继续

## 交互式模式

推荐新手使用交互式模式：

```bash
python -m src.cli -i
# 或
xhs2yt -i
```

**功能菜单：**
1. 单个视频搬运
2. 获取用户视频列表
3. 批量搬运上传
4. 更新凭证
5. 查看凭证状态
0. 退出

**特点：**
- 实时显示凭证状态
- 默认值提示，减少输入
- 操作确认，防止误操作
- 清屏刷新，界面整洁

## 测试

```bash
# 运行测试套件
python -m tests.test_flow
```

**测试内容：**
1. 凭证状态检查（验证 YouTube API 连接，不上传视频）
2. 视频流选择（去水印）
3. 标题提取
4. 视频下载
5. 搬运流程准备检查（验证 API 连接和元数据生成，不上传视频）
6. 受众分析测试（时区推荐、时间分析）

**注意：** 测试不会实际上传视频到 YouTube，仅验证 API 认证和下载功能。

## 开发约定

- 使用 `log_callback` 和 `progress_callback` 进行日志和进度回调
- 进度值范围：0-100
- 错误处理：返回 `(success: bool, message: str)` 元组
- 编码：UTF-8
- Python 版本：3.10+

## Git 开发规范

### 分支管理策略

```
master              # 主分支，稳定版本（测试通过）
├── feature/xxx     # 功能分支
├── fix/xxx         # 修复分支
├── refactor/xxx    # 重构分支
└── docs/xxx        # 文档分支
```

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

### 合并检查清单

- [ ] 代码已提交
- [ ] 回归测试通过 (`python -m tests.test_flow`)
- [ ] 无遗留的调试代码

## .gitignore

**敏感配置文件：**
- `cookies.txt`
- `credentials.json`
- `token.json`
- `scripts/email_config.sh`

**生成文件：**
- `cache/videos/*.mp4`
- `data/video_list.json`
- `data/uploaded.json`
- `data/timezone_cache.json`

**开发文件：**
- `__pycache__/`
- `*.pyc`
- `.venv/`

## 依赖

**核心依赖：**
```
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.0
google-api-python-client>=2.0.0
requests>=2.28.0
```

**可选依赖：**
```
openai>=1.0.0          # AI 翻译
playwright>=1.40.0     # Playwright 方式获取视频列表
pytest>=7.0.0          # 开发测试
```

## 测试参考

测试 URL（短链接）：
- `http://xhslink.com/o/6fDiSoovKl5` - 视频下载测试