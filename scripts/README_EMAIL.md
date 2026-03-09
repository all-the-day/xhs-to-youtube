# 邮件推送配置指南

## 快速开始

### 1. 配置邮箱

#### Gmail（推荐）

1. 开启两步验证：https://myaccount.google.com/security
2. 生成应用专用密码：https://myaccount.google.com/apppasswords
   - 选择"邮件"和"其他（自定义名称）"
   - 生成后复制 16 位密码（无空格）

3. 复制配置模板：
```bash
cd ~/xhs-to-youtube/scripts
cp email_config.example.sh email_config.sh
```

4. 编辑 `email_config.sh`，填入你的信息：
```bash
export DIGEST_SENDER_EMAIL="your-email@gmail.com"
export DIGEST_SENDER_PASSWORD="abcd efgh ijkl mnop"  # 16位应用密码
export DIGEST_RECIPIENTS="your-phone-email@carrier.com"  # 接收邮箱
```

#### QQ邮箱 / 163邮箱

1. 登录邮箱网页版
2. 进入设置 → 账户 → POP3/SMTP 服务
3. 开启服务并获取授权码
4. 使用对应配置（参考 `email_config.example.sh`）

### 2. 测试发送

```bash
# 加载配置
source ~/xhs-to-youtube/scripts/email_config.sh

# 发送今日日报
python3 ~/xhs-to-youtube/scripts/send_digest_email.py
```

### 3. 设置自动发送（可选）

添加到 crontab，每天早上 8 点自动发送：

```bash
crontab -e
```

添加以下行：
```
0 8 * * * source /home/duoban/xhs-to-youtube/scripts/email_config.sh && python3 /home/duoban/xhs-to-youtube/scripts/send_digest_email.py >> /home/duoban/digest/logs/email.log 2>&1
```

## 推送到手机

### 方案 1: 邮件通知

大多数手机邮件客户端支持新邮件通知：
- iOS: 设置 → 邮件 → 通知
- Android: Gmail 应用 → 设置 → 通知

### 方案 2: 推送到微信/钉钉

使用企业微信机器人或钉钉机器人：

1. 创建群机器人，获取 Webhook URL
2. 修改 `send_digest_email.py` 添加 Webhook 发送功能

### 方案 3: 短信通知

某些邮箱服务商支持短信通知（需额外配置）：
- 139 邮箱：手机号@139.com
- QQ 邮箱：开启短信提醒

## 常见问题

### Q: Gmail 提示"应用密码不正确"
A: 确保已开启两步验证，且密码中无空格

### Q: 发送失败，提示认证错误
A: 检查 SMTP 服务器地址和端口：
- Gmail: smtp.gmail.com:587
- QQ: smtp.qq.com:587
- 163: smtp.163.com:465

### Q: 如何发送到多个邮箱？
A: 用逗号分隔多个地址：
```bash
export DIGEST_RECIPIENTS="email1@example.com,email2@example.com"
```

## 安全提示

⚠️ **不要将 `email_config.sh` 提交到 Git 仓库！**

已在 `.gitignore` 中添加：
```
scripts/email_config.sh
```

## 高级配置

### 自定义 SMTP 端口

```bash
export DIGEST_SMTP_PORT="465"  # SSL 端口
```

### 自定义发件人名称

```bash
export DIGEST_SENDER_NAME="每日技术简报"
```
