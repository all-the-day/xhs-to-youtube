# xhs-to-youtube

小红书视频搬运到 YouTube 的自动化工具。项目提供命令行、批量处理、定时任务和 Telegram Bot 控制入口，适合做视频抓取、翻译、上传和调度。

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m src.cli -i
```

## 主要命令

- `python -m src.cli status` 查看 Cookie、Google OAuth 和 Token 状态
- `python -m src.cli transfer <xhs-url>` 搬运单个视频
- `python -m src.cli fetch <profile-url>` 抓取用户主页视频列表
- `python -m src.cli batch --input data/video_list.json` 批量搬运
- `python -m src.cli analyze` 分析受众数据并推荐发布时间
- `python -m src.cli notify --channel telegram` 测试 Telegram 通知连通性
- `python -m src.bot` 启动 Telegram Bot

## 配置文件

- `config/config.example.json` 是本地配置模板
- `cookies.txt` 存放小红书 Cookie
- `credentials.json` 存放 Google OAuth 客户端凭证
- `token.json` 存放首次授权后生成的 YouTube Token
- `spiritual_content` 可选配置用于联调 `readBiblecontext`，默认关闭
- `translation_api` 可选配置仅用于兜底翻译，默认关闭；主链路优先直接使用 `readBiblecontext /compose` 的英文版输出
- 部署和交接说明见 [docs/deploy-handoff.md](docs/deploy-handoff.md)

示例配置：

```json
{
  "spiritual_content": {
    "enabled": false,
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
  }
}
```

说明：

- 英文描述优先直接请求 `readBiblecontext /compose`，由它返回英文版短句。
- `translation_api` 只在英文版不可用时作为 fallback，不建议作为主翻译链路。

示例调度配置默认提供 3 个任务：

```json
{
  "schedule": {
    "tasks": [
      {"time": "08:00", "limit": 3, "enabled": true, "description": "早间上传"},
      {"time": "12:00", "limit": 3, "enabled": true, "description": "午间上传"},
      {"time": "20:00", "limit": 4, "enabled": true, "description": "晚间上传"}
    ]
  }
}
```

## Telegram Bot

Bot 当前支持这些命令：

- `/status` 查看今日上传状态
- `/tasks` 查看定时任务列表
- `/run [时间] [数量]` 手动触发上传
- `/update_token` 生成 YouTube 授权链接
- `/auth <授权码>` 用授权码完成 YouTube 授权
- `/token_status` 检查凭证状态
- `/notify_test [all|telegram|feishu]` 测试通知连通性

如果你只想测试通知链路，可以直接运行：

```bash
python -m src.cli notify --channel telegram
```

## 测试

运行测试：

```bash
python -m pytest -q
```

默认会跳过真实网络下载测试。若要启用，需要设置：

```bash
XHS_RUN_LIVE_TESTS=1 python -m pytest -q
```

## 注意事项

仓库会生成 `cache/`、`logs/` 和 `data/` 下的运行数据。`cookies.txt`、`credentials.json` 和 `token.json` 属于敏感文件，不要提交到版本库。
