# 小红书到 YouTube 视频搬运工具

## 项目概述

将小红书视频自动搬运到 YouTube 频道的 CLI 工具，支持定时调度、远程控制和属灵内容联调。

当前代码已实现的核心能力：
- 自动下载小红书视频，并优先选择无水印流
- 通过 YouTube OAuth 2.0 完成授权和视频上传
- 单个视频搬运与批量搬运
- 获取小红书用户主页下的视频列表
- 基于 YouTube Studio CSV 的受众分析与发布时间建议
- 非推荐时段上传前进行确认
- 每日上传限制检测，默认 10 个/天
- 交互式命令行界面
- **定时调度上传**：支持 crontab 集成，按配置时间自动上传
- **Telegram Bot 远程控制**：通过 Telegram 查看状态、触发上传、管理任务
- **多渠道通知**：支持 Telegram 和飞书 Webhook 通知
- **属灵内容联调**：与 readBiblecontext 服务联调，在视频描述中插入属灵短句
- **二维码授权**：支持扫码授权 YouTube OAuth，方便服务器环境使用

当前翻译能力说明：
- 已实现 `MyMemory` 英文翻译
- 读取 `config/config.json` 中的 `proxies` 配置
- 支持 `translation_api` 配置，可通过外部 API 翻译属灵内容块
- 未实现 DeepLX、DeepL、OpenAI 等翻译后端

**版本**: 1.5.0

## 技术栈

- Python 3.10+
- Google YouTube Data API v3
- OAuth 2.0
- requests
- Telegram Bot API

## 项目结构

```text
xhs-to-youtube/
├── AGENTS.md            # 项目说明
├── pyproject.toml       # 项目配置
├── main.py              # 入口脚本
├── upload.sh            # 批量上传包装脚本（调用 python3 -m src.cli batch）
├── xhs-bot.service      # systemd 服务配置（Telegram Bot）
├── cookies.txt          # 小红书 Cookie
├── credentials.json     # Google OAuth 凭证
├── token.json           # YouTube 访问令牌
├── src/
│   ├── __init__.py
│   ├── cli.py           # CLI 入口（argparse 子命令）
│   ├── core.py          # 核心协调类 XHSToYouTube
│   ├── config.py        # 路径、限制、调度配置等常量
│   ├── models.py        # dataclass 数据模型
│   ├── download.py      # 视频下载与无水印流选择
│   ├── upload.py        # YouTube 授权与上传
│   ├── fetch.py         # 用户视频列表获取
│   ├── translate.py     # MyMemory 翻译服务
│   ├── analyze.py       # 受众分析与发布时间建议
│   ├── interactive.py   # 交互式 CLI
│   ├── schedule.py      # 定时调度模块
│   ├── bot.py           # Telegram Bot 服务
│   ├── notification.py  # 通知模块（Telegram/飞书）
│   ├── spiritual_content.py  # 属灵内容客户端（readBiblecontext 联调）
│   └── utils/
│       ├── __init__.py
│       └── retry.py     # 重试工具装饰器
├── tests/
│   ├── __init__.py
│   ├── conftest.py      # pytest 配置（live_network marker）
│   ├── test_flow.py     # 主流程测试套件
│   └── test_spiritual_content.py  # 属灵内容联调测试
├── docs/
│   ├── deploy-handoff.md      # 部署与交接说明
│   └── server-execution.md    # 服务器执行顺序
├── config/
│   ├── config.example.json
│   └── config.json      # 运行时配置（代理、调度、通知、属灵内容）
├── cache/
│   └── videos/
├── logs/
│   └── schedule.log     # 调度日志
└── data/
    ├── video_list.json
    ├── uploaded.json
    ├── timezone_cache.json
    ├── cat_videos.json        # 分类视频列表
    ├── reupload_list.json     # 重传列表
    ├── 地理位置.../表格数据.csv
    └── 观看者年龄_观看者性别.../表格数据.csv
```

## 安装

```bash
cd xhs-to-youtube
pip install -e .
```

安装后可使用：

```bash
xhs2yt -i
python -m src.cli -i
```

说明：
- 某些环境只有 `python3`，示例中的 `python -m ...` 需要改成 `python3 -m ...`
- 可选开发依赖：`pip install -e .[dev]`

## 命令行使用

### 交互式模式

```bash
python -m src.cli -i
# 或
xhs2yt -i
```

### 搬运单个视频

```bash
# 默认不翻译
python -m src.cli transfer "https://www.xiaohongshu.com/explore/xxx"

# 翻译标题和描述
python -m src.cli transfer "小红书URL" --translate

# 仅翻译标题
python -m src.cli transfer "小红书URL" --translate-title

# 仅翻译描述
python -m src.cli transfer "小红书URL" --translate-desc

# 手动指定英文标题
python -m src.cli transfer "小红书URL" --title-en "English Title"

# 自定义描述和标签
python -m src.cli transfer "小红书URL" --desc "自定义描述" --tags "vlog,life,cute"

# 自定义隐私设置
python -m src.cli transfer "小红书URL" --privacy unlisted

# 保留本地视频
python -m src.cli transfer "小红书URL" --keep-video

# 启用发布时间检查与非推荐时段确认
python -m src.cli transfer "小红书URL" --time-confirm
```

### 获取用户视频列表

```bash
# 默认输出到 data/video_list.json
python -m src.cli fetch "https://www.xiaohongshu.com/user/profile/xxx"

# 自定义输出文件和每页数量
python -m src.cli fetch "用户主页URL" --page-size 20 -o my_videos.json
```

### 批量搬运上传

**重要变更**：批量上传默认不翻译，只做中文搬运。只有显式指定翻译参数才会翻译。

```bash
# 默认不翻译（中文搬运）
python -m src.cli batch

# 指定输入文件
python -m src.cli batch --input my_videos.json

# 启用翻译（标题+描述）
python -m src.cli batch --translate-title --translate-desc

# 仅翻译标题
python -m src.cli batch --translate-title

# 仅翻译描述
python -m src.cli batch --translate-desc

# 自定义间隔时间
python -m src.cli batch --interval-min 15 --interval-max 45

# 限制成功上传数量
python -m src.cli batch --limit 5

# 不跳过已上传记录
python -m src.cli batch --force

# 启用发布时间检查与非推荐时段确认
python -m src.cli batch --time-confirm
```

### 定时调度

```bash
# 列出所有定时任务配置
python -m src.cli schedule --list

# 显示今日调度状态
python -m src.cli schedule --status

# 手动执行定时上传（使用配置中的任务）
python -m src.cli schedule --time 08:00 --limit 3

# 生成 crontab 配置
python -m src.cli schedule --install-cron

# 指定 Python 路径生成 crontab
python -m src.cli schedule --install-cron --python-path /usr/bin/python3
```

### 受众分析

```bash
python -m src.cli analyze
python -m src.cli analyze --force --verbose
```

### 通知测试

```bash
# 测试所有通知通道
python -m src.cli notify

# 测试指定通道
python -m src.cli notify --channel telegram
python -m src.cli notify --channel feishu

# 自定义测试消息
python -m src.cli notify --message "测试通知内容"
```

### 凭证管理

```bash
python -m src.cli update
python -m src.cli update --cookie
python -m src.cli update --token
python -m src.cli status
```

### OAuth 授权方式

更新 Token 时支持三种授权方式：

1. **扫码授权（推荐）**：终端显示二维码，手机扫码授权
2. **图片扫码**：打开生成的 `auth_qrcode.png` 图片扫码
3. **链接授权**：复制授权链接到浏览器完成授权

### 包装脚本

```bash
./upload.sh 5
```

作用：
- 调用 `python3 -m src.cli batch --limit <数量>`
- 默认上传 5 个视频

## 属灵内容功能

### 功能说明

属灵内容功能允许在视频描述中插入来自 `readBiblecontext` 服务的属灵短句，包括：
- 短标题（如"安息与轻省"）
- 属灵短句（2-4 行）
- 圣经经文引用

### 配置要求

在 `config/config.json` 中配置：

```json
{
  "spiritual_content": {
    "enabled": true,
    "api_url": "http://127.0.0.1:8080",
    "api_key": "",
    "timeout": 15,
    "style": "normal"
  }
}
```

配置项说明：
- `enabled`: 是否启用属灵内容功能
- `api_url`: readBiblecontext 服务地址
- `api_key`: API 密钥（可选）
- `timeout`: 请求超时时间（秒）
- `style`: 内容风格（normal/gentle）

### 工作流程

1. **中文搬运**：调用 `readBiblecontext /compose` 获取中文属灵内容
2. **英文翻译**：如果启用翻译，会调用 `readBiblecontext /compose` 直接获取英文版属灵内容，或通过 `translation_api` 翻译

### 联调测试

```bash
# 运行属灵内容联调测试
python3 tests/test_spiritual_content.py
```

### 部署顺序

详见 `docs/deploy-handoff.md` 和 `docs/server-execution.md`：

1. 先部署 `readBiblecontext` 服务
2. 确认 `/health` 和 `/compose` 接口正常
3. 在 `xhs-to-youtube` 中启用 `spiritual_content.enabled=true`
4. 运行联调测试

## 定时调度功能

### 配置文件

定时任务配置位于 `config/config.json`：

```json
{
  "proxies": {},
  "schedule": {
    "tasks": [
      {"time": "08:00", "limit": 1, "enabled": true, "description": "早间上传"},
      {"time": "12:00", "limit": 1, "enabled": true, "description": "午间上传"},
      {"time": "20:00", "limit": 1, "enabled": true, "description": "晚间上传"}
    ],
    "default_limit": 3,
    "log_file": "logs/schedule.log",
    "notification": {
      "enabled": true,
      "telegram_token": "YOUR_BOT_TOKEN",
      "telegram_chat_id": "YOUR_CHAT_ID",
      "feishu_webhook": "",
      "notify_on_success": true,
      "notify_on_failure": true
    }
  }
}
```

### Crontab 集成

1. 生成 crontab 配置：
   ```bash
   python -m src.cli schedule --install-cron
   ```

2. 将输出添加到 crontab：
   ```bash
   crontab -e
   ```

示例 crontab 条目：
```cron
# 早间上传
0 8 * * * cd /home/iflow_space/xhs-to-youtube && python3 -m src.cli schedule --time 08:00 --limit 1 >> logs/cron.log 2>&1

# 午间上传
0 12 * * * cd /home/iflow_space/xhs-to-youtube && python3 -m src.cli schedule --time 12:00 --limit 1 >> logs/cron.log 2>&1

# 晚间上传
0 20 * * * cd /home/iflow_space/xhs-to-youtube && python3 -m src.cli schedule --time 20:00 --limit 1 >> logs/cron.log 2>&1
```

### 调度日志

调度执行日志保存在 `logs/schedule.log`，格式：
```
2026-03-29 08:00:15 - INFO - [08:00] 任务执行成功 - 计划: 1, 成功: 1, 跳过: 0, 失败: 0
```

## Telegram Bot 远程控制

### 启动 Bot

**方式一：直接运行**
```bash
python -m src.bot
```

**方式二：systemd 服务**
```bash
# 复制服务文件
sudo cp xhs-bot.service /etc/systemd/system/

# 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable xhs-bot
sudo systemctl start xhs-bot

# 查看状态
sudo systemctl status xhs-bot
```

### Bot 命令

| 命令 | 说明 |
|------|------|
| `/start` 或 `/help` | 显示帮助信息 |
| `/status` | 查看今日上传状态 |
| `/tasks` | 查看定时任务列表 |
| `/run [时间] [数量]` | 手动触发上传任务 |
| `/enable <时间>` | 启用指定任务 |
| `/disable <时间>` | 禁用指定任务 |

### 配置要求

在 `config/config.json` 中配置：
- `telegram_token`: Telegram Bot Token
- `telegram_chat_id`: 授权的 Chat ID

## 通知功能

### 支持的通知渠道

1. **Telegram**: 通过 Bot API 发送消息
2. **飞书**: 通过 Webhook 发送卡片消息

### 通知触发场景

- 定时任务执行成功/失败
- 手动触发上传结果
- Bot 启动通知

### 配置示例

```json
{
  "notification": {
    "enabled": true,
    "telegram_token": "YOUR_BOT_TOKEN",
    "telegram_chat_id": "YOUR_CHAT_ID",
    "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
    "notify_on_success": true,
    "notify_on_failure": true
  }
}
```

### 测试通知连通性

使用 `notify` 命令测试通知通道是否正常：

```bash
# 测试所有通道
python -m src.cli notify

# 测试 Telegram
python -m src.cli notify --channel telegram

# 测试飞书
python -m src.cli notify --channel feishu
```

## 核心模块

### `src/core.py`

`XHSToYouTube` 负责协调下载、翻译、上传、批量处理、时间建议和属灵内容。

主要方法：

| 方法 | 说明 |
|------|------|
| `transfer(xhs_url, ...)` | 单个视频搬运流程 |
| `batch_transfer(video_list_path, ...)` | 批量搬运，支持跳过已上传和数量限制 |
| `fetch_user_videos(user_url, ...)` | 获取用户主页视频列表 |
| `download_video(url, ...)` | 下载小红书视频 |
| `upload_to_youtube(...)` | 上传视频到 YouTube |
| `translate(text, target_type)` | 调用翻译服务 |
| `check_credentials()` | 检查 Cookie、OAuth 凭证和 Token 状态 |
| `update_cookie(content)` | 更新小红书 Cookie |
| `check_upload_limit()` | 检查每日上传限制 |
| `get_authorization_url()` | 获取 OAuth 授权链接 |
| `authorize_youtube_with_code(code)` | 使用授权码完成授权 |
| `generate_english_title(...)` | 生成英文标题 |
| `generate_description(...)` | 生成视频描述（含属灵内容） |
| `get_today_upload_count()` | 获取今日已上传数量 |
| `_show_time_suggestion()` | 上传前显示时间建议 |
| `_get_time_slot_info(hour)` | 按推荐时段返回时间段标签 |
| `_save_uploaded_record(record)` | 保存上传记录 |

注意：
- `transfer()` 在非推荐时段会询问是否继续上传（需启用 `--time-confirm`）
- `batch_transfer()` 默认不翻译，只做中文搬运
- `generate_description()` 会根据配置插入属灵内容

### `src/spiritual_content.py`

属灵内容客户端模块，负责与 `readBiblecontext` 服务联调。

主要组件：

| 组件 | 说明 |
|------|------|
| `SpiritualContentResult` | 属灵内容结果数据类 |
| `SpiritualContentClient` | 属灵内容客户端类 |

主要方法：

| 方法 | 说明 |
|------|------|
| `enabled()` | 检查属灵内容功能是否启用 |
| `compose(text, tags, context, length, target_lang)` | 获取属灵短句 |

使用示例：
```python
from src.spiritual_content import SpiritualContentClient

client = SpiritualContentClient()
if client.enabled():
    result = client.compose(
        text="今天很喜悦",
        tags=["日常"],
        context="vlog",
        length=4,
        target_lang="zh"
    )
    if result:
        print(result.short_title)
        print(result.lines)
        print(result.references)
```

### `src/schedule.py`

定时调度模块，提供定时上传功能的执行逻辑。

主要函数：

| 函数 | 说明 |
|------|------|
| `run_scheduled_upload(time_str, limit, log_callback)` | 执行定时上传任务 |
| `list_schedule_tasks()` | 列出所有调度任务 |
| `generate_crontab_entries(python_path)` | 生成 crontab 配置 |
| `get_today_schedule_status()` | 获取今日调度状态 |
| `setup_schedule_logger()` | 设置调度日志记录器 |
| `log_execution(logger, task, result, error)` | 记录执行结果 |

### `src/bot.py`

Telegram Bot 服务模块，提供远程控制和状态查询功能。

主要函数：

| 函数 | 说明 |
|------|------|
| `run_bot()` | 运行 Bot 主循环 |
| `handle_command(command, args, chat_id)` | 处理 Bot 命令 |
| `get_status_message()` | 获取状态消息 |
| `get_tasks_message()` | 获取任务列表消息 |
| `handle_run_command(args)` | 处理 run 命令 |
| `handle_enable_command(args, enable)` | 处理 enable/disable 命令 |
| `send_message(text, chat_id)` | 发送 Telegram 消息 |

### `src/notification.py`

通知模块，提供多渠道消息发送功能。

主要函数：

| 函数 | 说明 |
|------|------|
| `send_notification(message, level, title)` | 发送通知（统一入口） |
| `send_telegram_message(token, chat_id, message, level, title)` | 发送 Telegram 消息 |
| `send_feishu_message(webhook, message, level, title)` | 发送飞书消息 |
| `notify_upload_result(task_time, result, error)` | 发送上传结果通知 |
| `notify_daily_summary(today_uploads, tasks_status)` | 发送每日汇总通知 |
| `test_notification_delivery(message, channel)` | 测试通知通道连通性 |

### `src/utils/retry.py`

重试工具模块，提供通用的重试装饰器。

主要组件：

| 组件 | 说明 |
|------|------|
| `RetryExhaustedError` | 重试次数耗尽异常 |
| `with_retry(max_retries, backoff, exceptions, on_retry)` | 重试装饰器 |
| `retry_call(func, args, kwargs, ...)` | 带重试的函数调用 |

使用示例：
```python
from src.utils.retry import with_retry, retry_call

# 装饰器方式
@with_retry(max_retries=3, backoff=2.0, exceptions=(requests.Timeout,))
def fetch_data():
    return requests.get("https://example.com", timeout=10)

# 函数调用方式
result = retry_call(
    requests.get,
    args=("https://example.com",),
    kwargs={"timeout": 10},
    max_retries=3,
    exceptions=(requests.Timeout,)
)
```

### `src/analyze.py`

受众分析模块，基于 YouTube Studio 导出的 CSV 文件：
- 查找地理位置目录下的 `表格数据.csv`
- 查找年龄/性别目录下的 `表格数据.csv`
- 解析地区、年龄、性别分布
- 生成最佳发布时间、次选时间和受众洞察
- 将结果缓存到 `data/timezone_cache.json`

主要函数：

| 函数 | 说明 |
|------|------|
| `analyze_and_cache(force, log_callback)` | 分析并缓存受众数据 |
| `get_time_recommendation()` | 获取时间推荐 |
| `is_good_upload_time(hour)` | 判断当前是否在推荐时段 |
| `format_audience_report(cache, hour)` | 格式化完整分析报告 |
| `format_time_suggestion(rec, hour)` | 格式化上传前提示 |
| `calculate_best_upload_time(regions, demographics)` | 计算发布时间建议 |
| `calculate_audience_insight(demographics, regions)` | 计算受众洞察 |
| `load_audience_cache()` | 加载缓存 |
| `save_audience_cache(cache)` | 保存缓存 |

### `src/download.py`

下载模块负责：
- 解析小红书页面
- 提取视频信息（标题、描述、时长）
- 优先选择无水印流（通过 `streamDesc` 判断是否包含 `WM` 标记）
- 下载视频到缓存目录

### `src/upload.py`

上传模块负责：
- 检查 `credentials.json` 和 `token.json`
- 获取或刷新 YouTube OAuth 凭证
- 支持两种授权方式：本地服务器自动授权和手动输入授权码
- 上传视频到 YouTube

### `src/fetch.py`

视频列表获取模块当前支持两种方式：
1. API 方式：优先调用小红书接口获取分页数据
2. 页面解析：当 API 返回异常时回退到 HTML 解析

当前未实现 Playwright 抓取流程。

### `src/translate.py`

翻译服务支持：
- `MyMemory` 翻译（默认）
- `translation_api` 配置（可选，用于翻译属灵内容块）

主要功能：
- 请求 `https://api.mymemory.translated.net/get`
- 翻译方向固定为 `zh-CN -> en`
- 失败时返回原文
- 支持从配置文件读取代理

### `src/interactive.py`

交互式 CLI 提供：
- 凭证状态摘要
- 单个视频搬运
- 获取用户视频列表
- 批量搬运上传
- 更新凭证
- 查看凭证状态

## 受众分析功能

### 数据来源

从 YouTube Studio 导出以下 CSV：
1. 地理位置
2. 观看者年龄 / 观看者性别

当前代码会在 `data/` 下查找：
- 目录名包含 `地理位置` 的目录，并读取其中的 `表格数据.csv`
- 目录名包含 `年龄` 或 `性别` 的目录，并读取其中的 `表格数据.csv`

### 分析维度

- 地理位置占比与主要时区
- 年龄分布与性别分布
- 年龄 x 性别交叉数据
- 基于地区和年龄作息规律的发布时间建议
- 受众画像内容建议

### 发布时间提示

单视频搬运时（启用 `--time-confirm`）会先显示时间建议：
- 黄金时段和次选时段自动继续
- 非推荐时段会询问 `是否继续上传? [y/N]`

### 缓存行为

`analyze_and_cache()` 会比较：
- 源文件路径
- 文件修改时间
- 文件 MD5

有变化或传入 `force=True` 时重新分析并写入 `data/timezone_cache.json`。

## 配置文件

### `cookies.txt`

支持两种输入格式：
- JSON Cookie 导出内容
- Netscape Cookie 文件内容

`update_cookie()` 会将 JSON 格式转换为 Netscape 格式后保存。

### `credentials.json`

Google Cloud Console 下载的 OAuth 客户端凭证文件。

### `token.json`

授权后自动生成的访问令牌文件。

### `config/config.json`

完整配置示例：

```json
{
  "proxies": {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890"
  },
  "spiritual_content": {
    "enabled": true,
    "api_url": "http://127.0.0.1:8080",
    "api_key": "",
    "timeout": 15,
    "style": "normal"
  },
  "translation_api": {
    "enabled": false,
    "api_url": "http://127.0.0.1:8080",
    "api_key": "",
    "timeout": 15,
    "source_lang": "zh-CN",
    "target_lang": "en",
    "mode": "spiritual",
    "preserve_lines": true
  },
  "schedule": {
    "tasks": [
      {"time": "08:00", "limit": 1, "enabled": true, "description": "早间上传"},
      {"time": "12:00", "limit": 1, "enabled": true, "description": "午间上传"},
      {"time": "20:00", "limit": 1, "enabled": true, "description": "晚间上传"}
    ],
    "default_limit": 3,
    "log_file": "logs/schedule.log",
    "notification": {
      "enabled": true,
      "telegram_token": "YOUR_BOT_TOKEN",
      "telegram_chat_id": "YOUR_CHAT_ID",
      "feishu_webhook": "",
      "notify_on_success": true,
      "notify_on_failure": true
    }
  }
}
```

参考示例文件：`config/config.example.json`

## 数据结构

### `fetch_user_videos()` 返回结构

```json
{
  "user_id": "用户ID",
  "fetch_time": "2026-02-16 09:27:07",
  "total_count": 4,
  "videos": [
    {
      "note_id": "笔记ID",
      "title": "视频标题",
      "url": "https://www.xiaohongshu.com/user/profile/xxx/yyy?xsec_token=xxx&xsec_source=pc_user",
      "xsec_token": "访问令牌",
      "desc": "视频描述"
    }
  ]
}
```

### `batch_transfer()` 返回结构

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

说明：
- 当当天上传配额耗尽时，返回中会包含 `error` 和 `message`
- 当批量过程中命中 YouTube 上传限制时，结果中可能包含 `limit_exceeded`

### `uploaded.json` 当前实际结构

```json
{
  "records": {
    "note_id": {
      "youtube_id": "shaLodkyKS4",
      "youtube_url": "https://www.youtube.com/watch?v=shaLodkyKS4",
      "title": "翻译后的英文标题",
      "uploaded_at": "2026-03-04 19:09:33"
    }
  }
}
```

注意：
- `UploadRecord` 数据类包含 `upload_hour`、`time_slot`、`recommendation_followed`
- 但 `_save_uploaded_record()` 当前不会把这三个字段写入 `uploaded.json`

### 数据类定义

```python
@dataclass
class CredentialStatus:
    name: str
    exists: bool
    valid: bool
    message: str
    path: str

@dataclass
class UploadRecord:
    note_id: str
    youtube_id: str
    youtube_url: str
    title: str
    uploaded_at: str
    upload_hour: int | None = None
    time_slot: str | None = None
    recommendation_followed: bool | None = None

@dataclass
class AudienceRegion:
    code: str
    views: int
    weight: float
    timezone: str

@dataclass
class AgeGroup:
    age_range: str
    views_percent: float
    watch_time_percent: float

@dataclass
class GenderData:
    gender: str
    views_percent: float
    watch_time_percent: float

@dataclass
class DemographicsData:
    age_groups: list[AgeGroup]
    genders: list[GenderData]
    age_gender_breakdown: list[dict]

@dataclass
class TimeRecommendation:
    optimal_time: str
    secondary_time: str
    user_timezone: str
    primary_tz_weight: float
    reason: str

@dataclass
class AudienceInsight:
    primary_age_group: str
    primary_age_percent: float
    gender_ratio: str
    dominant_gender: str
    content_suggestion: str

@dataclass
class AudienceCache:
    geo_source_file: str = ""
    geo_source_mtime: float = 0
    geo_source_md5: str = ""
    demo_source_file: str = ""
    demo_source_mtime: float = 0
    demo_source_md5: str = ""
    analyzed_at: str = ""
    total_views: int = 0
    regions: list[AudienceRegion] = field(default_factory=list)
    demographics: DemographicsData | None = None
    recommendation: TimeRecommendation | None = None
    insight: AudienceInsight | None = None

@dataclass
class SpiritualContentResult:
    short_title: str
    lines: list[str]
    references: list[str]
    confidence: float = 0.0
    theme: str = ""
    source_hits: list[dict[str, Any]] | None = None
```

兼容别名：
- `TimezoneCache = AudienceCache`

## 去水印功能

当前实现会在页面数据中选择视频流：
- 解析 `h264` 和 `h265` 编码的视频流列表
- 通过 `streamDesc` 字段判断是否包含 `WM` 标记
- 优先选择无水印版本，必要时回退到有水印版本

## 每日上传限制

默认限制定义在 `src/config.py`：

```python
DAILY_UPLOAD_LIMIT = 10
```

达到限制时：
- 批量上传前会先检查当天已上传数量
- 如果剩余配额为 0，批量任务直接停止
- 处理中若触发 YouTube 上传限制，也会提前中断

## 交互式模式

推荐使用：

```bash
python -m src.cli -i
```

菜单项：
1. 单个视频搬运
2. 获取用户视频列表
3. 批量搬运上传
4. 更新凭证
5. 查看凭证状态
0. 退出

## 测试

### 运行测试

```bash
# 运行主流程测试
python -m pytest tests/test_flow.py -v

# 运行属灵内容联调测试
python -m pytest tests/test_spiritual_content.py -v

# 运行所有测试
python -m pytest tests/ -v
```

某些环境下需要：

```bash
python3 -m pytest tests/ -v
```

### 真实网络测试

部分测试需要真实网络访问，默认会跳过。要运行这些测试：

```bash
XHS_RUN_LIVE_TESTS=1 python -m pytest tests/test_flow.py -v -m live_network
```

### 测试覆盖

当前测试覆盖：
1. 凭证状态检查
2. 视频流选择（去水印）
3. 标题提取
4. 视频下载
5. 搬运流程准备检查
6. 时间推荐功能
7. 时间段标签
8. 上传记录数据结构
9. 属灵内容客户端
10. 属灵内容描述生成
11. 翻译服务

注意：
- 测试不会实际上传 YouTube 视频
- 部分测试依赖真实网络、Cookie、OAuth 凭证和外部页面可访问性

## 开发约定

- 使用 `log_callback` 和 `progress_callback`
- 进度范围为 `0-100`
- 路径处理使用 `pathlib.Path`
- 数据模型使用 `dataclass`
- 编码为 UTF-8
- Python 版本要求为 3.10+

补充说明：
- 代码中的错误返回风格并不完全统一，既有返回字典的路径，也有直接抛出异常的路径
- 文档应以当前实现行为为准，不应假定所有接口都统一返回 `(success, message)` 元组

## Git 开发规范

### 分支管理策略

```text
master
├── feature/xxx
├── fix/xxx
├── refactor/xxx
└── docs/xxx
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
| `chore` | 构建或工具变更 |

### 合并检查清单

- [ ] 代码已提交
- [ ] 回归测试通过
- [ ] 无遗留调试代码

## 依赖

### 核心依赖

```text
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.0
google-api-python-client>=2.0.0
requests>=2.28.0
pyperclip>=1.8.0
qrcode>=7.4.0
```

### 可选依赖

```text
pytest>=7.0.0      # dev 组
openai>=1.0.0      # translate 组（未实现）
```

说明：
- 当前 `pyproject.toml` 中声明 `translate` 可选依赖为 `openai>=1.0.0`，但代码未使用 OpenAI 翻译
- 文档不应将该依赖描述为当前可用功能

## 部署文档

### 部署与交接说明

详见 `docs/deploy-handoff.md`：
- `readBiblecontext` 和 `xhs-to-youtube` 联调部署
- 服务启动顺序
- 验证步骤

### 服务器执行顺序

详见 `docs/server-execution.md`：
- 快速启动指南
- 中文属灵内容配置
- 测试样例

## 测试参考

测试 URL（短链接）：
- `http://xhslink.com/o/6fDiSoovKl5`