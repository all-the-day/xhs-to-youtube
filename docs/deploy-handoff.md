# 部署与交接说明

这份文档用于把 `readBiblecontext` 和 `xhs-to-youtube` 一起推到服务器后，按顺序拉起、验证，并交给后续 agent 继续执行。

## 目标

- 先让 `readBiblecontext` 作为独立轻量服务稳定运行。
- 再让 `xhs-to-youtube` 通过 `spiritual_content` 选项联调这个服务。
- 最后由后续 agent 在服务器上做真实内容测试和策略微调。

## 当前约定

- `readBiblecontext` 负责：
  - 圣经查询
  - 生命读经查询
  - 晨兴查询
  - 灵粮内容检索
  - `/compose` 属灵短句生成
- `xhs-to-youtube` 负责：
  - 小红书视频抓取
  - 下载
  - 上传 YouTube
  - 在描述里可选插入 `readBiblecontext` 返回的属灵短句
  - 提供 CLI 和 Web 控制台两种操作入口

## 部署顺序

### 1. 先拉 `readBiblecontext`

服务器上先部署 `readBiblecontext`，确认下面资源可用：

- `data/raw/bible_root/bible.db`
- `data/raw/life_study/生命读经索引.json`
- `data/raw/life_study/生命读经章节映射.json`
- `data/raw/morning_revival/晨兴状态.json`

如果使用 Docker：

```bash
docker compose up -d --build
```

如果使用 `systemd`：

```bash
sudo systemctl daemon-reload
sudo systemctl enable readbiblecontext
sudo systemctl start readbiblecontext
```

健康检查：

```bash
curl http://127.0.0.1:8080/health
curl -X POST http://127.0.0.1:8080/compose \
  -H 'Content-Type: application/json' \
  -d '{"text":"今天很喜悦","tags":["日常"],"context":"vlog","length":4}'
```

### 2. 再拉 `xhs-to-youtube`

在 `xhs-to-youtube/config/config.json` 里补上：

```json
{
  "spiritual_content": {
    "enabled": true,
    "api_url": "http://你的readBiblecontext地址:端口",
    "api_key": "",
    "timeout": 15,
    "style": "normal"
  }
}
```

说明：

- 英文描述优先直接请求 `readBiblecontext /compose`，由它返回 `target_lang=en` 的英文版短句。
- `translation_api` 只作为 fallback，不建议作为主链路。

如果暂时还没有 `readBiblecontext` 地址，就保持：

- `enabled: false`

### 3. 如需 Web 控制台，再做一次安全配置

`xhs-to-youtube` 的 Web 控制台默认可以启动，但部署到服务器前建议先补下面配置：

```json
{
  "web": {
    "enabled": true,
    "username": "admin",
    "password": "change-me",
    "csrf_enabled": true,
    "secret_key": "replace-with-random-string",
    "realm": "xhs-to-youtube web console"
  }
}
```

建议：

- 只监听 `127.0.0.1`，再用 Nginx / Caddy / 内网访问转发
- `web.enabled=true` 时，`web.username` 和 `web.password` 都必须配置
- 不要把 Web 端口直接暴露到公网
- `secret_key` 需要稳定且随机，不要频繁更换，否则会话和 CSRF 令牌会失效
- 如果只是本地桌面访问，可以把 `web.enabled` 保持为 `false`

联调检查：

```bash
python3 tests/test_spiritual_content.py
```

## 推荐验证顺序

建议先用下面三条内容验证输出风格：

- `今天很喜悦`
- `今天需要平安`
- `今天有点疲惫`

重点看：

- `short_title` 是否自然
- `lines` 是否过长
- `references` 是否优先 Bible
- `joy / peace / comfort` 是否还带出太重的信息腔
- `translation_api` 是否只在英文版不可用时兜底

## 后续 agent 的执行顺序

如果把两个仓库都已经推到服务器，后续 agent 按下面顺序做事即可：

1. 确认 `readBiblecontext` 服务状态和 `/health` 输出。
2. 确认 `readBiblecontext /compose` 返回正常。
3. 在 `xhs-to-youtube` 开启 `spiritual_content.enabled=true`。
4. 跑 `tests/test_spiritual_content.py`。
5. 用真实视频标题和描述测试 `generate_description()`。
6. 只在必要时继续微调 `readBiblecontext/src/readbiblecontext/api/service.py` 的主题策略。

## 当前内容策略

目前轻主题已经按下面顺序处理：

- `joy / peace / comfort` 优先 Bible
- 再回退到其他内容来源
- 最后才用模板兜底

这意味着：

- 日常类输入不会轻易被晨兴长篇带偏
- 输出会尽量短、稳、纯正
- 后面如果还要更轻，只需要继续调 `readBiblecontext` 的 `service.py`

## 注意事项

- `data/derived/` 不要提交到 git，派生库可重建。
- `xhs-to-youtube` 里 `spiritual_content` 默认关闭，不影响原有搬运流程。
- 先确保服务能跑，再做内容微调，不要把两步混在一起。

## 最后

这份文档的定位是“服务器部署与 agent 交接说明”，不是开发说明。
如果后续要继续改内容策略，优先改 `readBiblecontext`，`xhs-to-youtube` 只保留薄调用层。
