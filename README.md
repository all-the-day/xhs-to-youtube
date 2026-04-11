# xhs-to-youtube

小红书视频搬运到 YouTube 的自动化工具。项目提供命令行、批量处理、定时任务和 Telegram Bot 控制入口，适合做视频抓取、翻译、上传和调度。

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,translate]'
python -m src.cli -i
```

## 主要命令

- `python -m src.cli status` 查看 Cookie、Google OAuth 和 Token 状态
- `python -m src.cli transfer <xhs-url>` 搬运单个视频
- `python -m src.cli fetch <profile-url>` 抓取用户主页视频列表
- `python -m src.cli batch --input data/video_list.json` 批量搬运
- `python -m src.cli analyze` 分析受众数据并推荐发布时间
- `python -m src.bot` 启动 Telegram Bot

## 配置文件

- `config/config.example.json` 是本地配置模板
- `cookies.txt` 存放小红书 Cookie
- `credentials.json` 存放 Google OAuth 客户端凭证
- `token.json` 存放首次授权后生成的 YouTube Token

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
