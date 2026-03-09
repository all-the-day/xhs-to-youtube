#!/bin/bash
# 邮件发送配置示例
# 使用方法: 复制此文件为 email_config.sh，修改配置后 source email_config.sh

# ===== Gmail 配置示例 =====
# Gmail 需要使用应用专用密码，不是账户密码
# 生成方法: https://myaccount.google.com/apppasswords

export DIGEST_SMTP_SERVER="smtp.gmail.com"
export DIGEST_SMTP_PORT="587"
export DIGEST_SENDER_EMAIL="your-email@gmail.com"
export DIGEST_SENDER_PASSWORD="your-app-password"  # 16位应用密码，无空格
export DIGEST_SENDER_NAME="每日技术信息"
export DIGEST_RECIPIENTS="recipient@example.com"

# ===== QQ 邮箱配置示例 =====
# QQ邮箱需要开启 SMTP 服务并获取授权码
# 设置路径: 设置 -> 账户 -> POP3/SMTP服务

# export DIGEST_SMTP_SERVER="smtp.qq.com"
# export DIGEST_SMTP_PORT="587"
# export DIGEST_SENDER_EMAIL="your-email@qq.com"
# export DIGEST_SENDER_PASSWORD="authorization-code"  # 授权码，非QQ密码
# export DIGEST_SENDER_NAME="每日技术信息"
# export DIGEST_RECIPIENTS="recipient@example.com"

# ===== 163 邮箱配置示例 =====
# 163邮箱需要开启 SMTP 服务并获取授权码

# export DIGEST_SMTP_SERVER="smtp.163.com"
# export DIGEST_SMTP_PORT="465"
# export DIGEST_SENDER_EMAIL="your-email@163.com"
# export DIGEST_SENDER_PASSWORD="authorization-code"
# export DIGEST_SENDER_NAME="每日技术信息"
# export DIGEST_RECIPIENTS="recipient@example.com"

# ===== Outlook/Hotmail 配置示例 =====

# export DIGEST_SMTP_SERVER="smtp-mail.outlook.com"
# export DIGEST_SMTP_PORT="587"
# export DIGEST_SENDER_EMAIL="your-email@outlook.com"
# export DIGEST_SENDER_PASSWORD="your-password"
# export DIGEST_SENDER_NAME="每日技术信息"
# export DIGEST_RECIPIENTS="recipient@example.com"
