#!/bin/bash
# 快速配置邮件推送

set -e

echo "======================================"
echo "  邮件推送快速配置向导"
echo "======================================"
echo ""

CONFIG_FILE="$(dirname "$0")/email_config.sh"

if [ -f "$CONFIG_FILE" ]; then
    echo "⚠️  配置文件已存在: $CONFIG_FILE"
    read -p "是否覆盖？ (y/N): " overwrite
    if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
fi

echo ""
echo "请选择邮箱服务商："
echo "  1) Gmail (推荐)"
echo "  2) QQ 邮箱"
echo "  3) 163 邮箱"
echo "  4) Outlook/Hotmail"
echo "  5) 自定义"
echo ""
read -p "请输入选项 (1-5): " choice

case $choice in
    1)
        SMTP_SERVER="smtp.gmail.com"
        SMTP_PORT="587"
        echo ""
        echo "📧 Gmail 配置"
        echo "提示: 需要先开启两步验证并生成应用专用密码"
        echo "生成地址: https://myaccount.google.com/apppasswords"
        echo ""
        ;;
    2)
        SMTP_SERVER="smtp.qq.com"
        SMTP_PORT="587"
        echo ""
        echo "📧 QQ 邮箱配置"
        echo "提示: 需要开启 SMTP 服务并获取授权码"
        echo "设置路径: 设置 → 账户 → POP3/SMTP服务"
        echo ""
        ;;
    3)
        SMTP_SERVER="smtp.163.com"
        SMTP_PORT="465"
        echo ""
        echo "📧 163 邮箱配置"
        echo "提示: 需要开启 SMTP 服务并获取授权码"
        echo ""
        ;;
    4)
        SMTP_SERVER="smtp-mail.outlook.com"
        SMTP_PORT="587"
        echo ""
        echo "📧 Outlook/Hotmail 配置"
        echo ""
        ;;
    5)
        echo ""
        read -p "SMTP 服务器地址: " SMTP_SERVER
        read -p "SMTP 端口 (默认 587): " SMTP_PORT
        SMTP_PORT=${SMTP_PORT:-587}
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac

echo ""
read -p "发件人邮箱: " SENDER_EMAIL
read -p "应用密码/授权码: " SENDER_PASSWORD
read -p "发件人名称 (默认: 每日技术信息): " SENDER_NAME
SENDER_NAME=${SENDER_NAME:-每日技术信息}

echo ""
echo "收件人邮箱 (可以是多个，用空格分隔):"
read -p "> " recipients

# 转换为逗号分隔
RECIPIENTS=$(echo $recipients | tr ' ' ',')

# 生成配置文件
cat > "$CONFIG_FILE" << EOF
#!/bin/bash
# 邮件发送配置 - 自动生成于 $(date '+%Y-%m-%d %H:%M:%S')

export DIGEST_SMTP_SERVER="$SMTP_SERVER"
export DIGEST_SMTP_PORT="$SMTP_PORT"
export DIGEST_SENDER_EMAIL="$SENDER_EMAIL"
export DIGEST_SENDER_PASSWORD="$SENDER_PASSWORD"
export DIGEST_SENDER_NAME="$SENDER_NAME"
export DIGEST_RECIPIENTS="$RECIPIENTS"
EOF

chmod 600 "$CONFIG_FILE"

echo ""
echo "✅ 配置完成！"
echo ""
echo "配置文件: $CONFIG_FILE"
echo ""
echo "下一步："
echo "  1. 测试发送: source $CONFIG_FILE && python3 $(dirname "$0")/send_digest_email.py"
echo "  2. 设置自动发送: 参考 $(dirname "$0")/README_EMAIL.md"
echo ""
