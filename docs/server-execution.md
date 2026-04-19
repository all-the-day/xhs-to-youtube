# 服务器执行版

这份文档只保留服务器上直接执行的顺序，目标是：

- 先拉起 `readBiblecontext`
- 再让 `xhs-to-youtube` 直接消费它的中文属灵内容
- 如需浏览器操作，再单独启动 `xhs-to-youtube` 的 Web 控制台

## 1. `readBiblecontext` 先起服务

确认服务器上有这些文件：

- `bible.db`
- `bible_kjv.db`
- `data/raw/life_study/生命读经索引.json`
- `data/raw/life_study/生命读经章节映射.json`
- `data/raw/morning_revival/晨兴状态.json`

启动方式二选一：

```bash
cd /path/to/readBiblecontext
PYTHONPATH=/path/to/readBiblecontext/src \
uvicorn readbiblecontext.api.app:app \
  --host 0.0.0.0 \
  --port 8080 \
  --app-dir /path/to/readBiblecontext/src
```

或者用服务器上的 systemd / Docker 方式启动。

先验证这几个接口：

```bash
curl http://127.0.0.1:8080/health
curl "http://127.0.0.1:8080/verse?book=创世记&ref=1:1"
curl "http://127.0.0.1:8080/verse?book=创世记&ref=1:1&lang=en"
curl -X POST http://127.0.0.1:8080/compose \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: change-me' \
  -d '{"text":"今天很喜悦","tags":["日常"],"length":4}'
```

## 2. `xhs-to-youtube` 再接入

在 `xhs-to-youtube/config/config.json` 里至少启用：

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

说明：

- 只保留中文属灵内容，不再默认启用英文翻译链路。

联调命令：

```bash
cd /path/to/xhs-to-youtube
python3 tests/test_spiritual_content.py
```

## 3. 推荐测试样例

先用这三条内容看输出风格：

- `今天很喜悦`
- `今天需要平安`
- `今天有点疲惫`

重点检查：

- `short_title` 是否自然
- `lines` 是否过长
- `references` 是否优先 Bible
- 中文内容是否简洁、自然、适合中午发布

## 4. 后续 agent 顺序

1. 确认 `readBiblecontext /health` 正常。
2. 确认 `verse` 和 `compose` 中文都正常。
3. 打开 `xhs-to-youtube` 的 `spiritual_content.enabled=true`。
4. 先跑 `tests/test_spiritual_content.py`。
5. 再用真实视频标题和描述测 `generate_description()`。
6. 只在必要时再微调 `readBiblecontext/src/readbiblecontext/api/service.py`。

## 5. 约束

- `xhs-to-youtube` 不再默认走翻译链路。
- 先把中文中午内容跑稳。
- 先跑通服务，再调风格。

## 6. Web 控制台

如果要在服务器上用浏览器操作 `xhs-to-youtube`，可以启动 Web 控制台：

```bash
cd /path/to/xhs-to-youtube
python -m src.cli web --host 127.0.0.1 --port 5000
```

建议做法：

- 只监听 `127.0.0.1`，再通过反向代理暴露给内网或 VPN
- 在 `config/config.json` 里配置 `web.enabled=true`、`web.username` 和 `web.password`
- 如需表单校验，再打开 `web.csrf_enabled=true`
- `web.secret_key` 建议设置为随机值，不要留空

当前 Web 控制台提供的入口：

- 凭证状态查看
- 单视频搬运
- 用户视频抓取
- 批量搬运
- YouTube 授权
- Cookie 更新
- 调度任务执行

注意：

- 没有登录鉴权时，不要把端口直接暴露到公网
- POST 表单开启 CSRF 后，必须通过页面提交，不要手工构造请求
