#!/usr/bin/env python3
"""
每日技术信息邮件推送脚本
支持发送日报和 GitHub 热门项目到邮箱
"""

import smtplib
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from datetime import datetime
from pathlib import Path


class EmailSender:
    """邮件发送器"""
    
    def __init__(self, config):
        self.smtp_server = config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = config.get('smtp_port', 587)
        self.sender_email = config['sender_email']
        self.sender_password = config['sender_password']
        self.sender_name = config.get('sender_name', 'Digest Bot')
        self.recipients = config['recipients']
        
    def send_email(self, subject, text_content, html_content=None):
        """发送邮件"""
        msg = MIMEMultipart('alternative')
        msg['From'] = formataddr((self.sender_name, self.sender_email))
        msg['To'] = ', '.join(self.recipients)
        msg['Subject'] = subject
        
        # 纯文本版本
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        
        # HTML 版本（如果提供）
        if html_content:
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, self.recipients, msg.as_string())
            server.quit()
            return True, "邮件发送成功"
        except Exception as e:
            return False, f"邮件发送失败: {str(e)}"


def load_markdown_file(file_path):
    """加载 Markdown 文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None


def markdown_to_html(markdown_text, title):
    """将 Markdown 转换为简单的 HTML"""
    import re
    
    html_lines = [f'<html><head><meta charset="utf-8"><title>{title}</title>']
    html_lines.append('<style>')
    html_lines.append('body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }')
    html_lines.append('h1, h2, h3 { color: #2c3e50; }')
    html_lines.append('h1 { border-bottom: 3px solid #3498db; padding-bottom: 10px; }')
    html_lines.append('h2 { border-bottom: 2px solid #95a5a6; padding-bottom: 8px; margin-top: 30px; }')
    html_lines.append('a { color: #3498db; text-decoration: none; }')
    html_lines.append('a:hover { text-decoration: underline; }')
    html_lines.append('code { background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 14px; }')
    html_lines.append('pre { background-color: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }')
    html_lines.append('blockquote { border-left: 4px solid #3498db; margin: 20px 0; padding-left: 20px; color: #7f8c8d; }')
    html_lines.append('.highlight { background-color: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; }')
    html_lines.append('</style></head><body>')
    
    # 简单的 Markdown 到 HTML 转换
    in_list = False
    for line in markdown_text.split('\n'):
        stripped = line.strip()
        
        # 标题
        if stripped.startswith('# '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h1>{stripped[2:]}</h1>')
        elif stripped.startswith('## '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h2>{stripped[3:]}</h2>')
        elif stripped.startswith('### '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h3>{stripped[4:]}</h3>')
        # 列表项
        elif stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            # 处理粗体和链接
            processed = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', stripped[2:])
            processed = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', processed)
            html_lines.append(f'<li>{processed}</li>')
        # 空行
        elif not stripped:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('')
        # 普通段落
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            # 处理粗体和链接
            processed = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', stripped)
            processed = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', processed)
            html_lines.append(f'<p>{processed}</p>')
    
    if in_list:
        html_lines.append('</ul>')
    
    html_lines.append('</body></html>')
    return '\n'.join(html_lines)


def send_daily_digest(email_config, date_str=None):
    """发送每日技术信息"""
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    digest_dir = Path.home() / 'digest'
    daily_file = digest_dir / 'daily' / f'{date_str}.md'
    github_file = digest_dir / 'github-trending' / f'{date_str}.md'
    
    sender = EmailSender(email_config)
    
    # 发送日报
    daily_content = load_markdown_file(daily_file)
    if daily_content:
        subject = f'📰 每日技术信息 - {date_str}'
        html_content = markdown_to_html(daily_content, subject)
        success, msg = sender.send_email(subject, daily_content, html_content)
        print(f"[日报] {msg}")
    else:
        print(f"[日报] 文件不存在: {daily_file}")
    
    # 发送 GitHub 热门
    github_content = load_markdown_file(github_file)
    if github_content:
        subject = f'🔥 GitHub 热门项目 - {date_str}'
        html_content = markdown_to_html(github_content, subject)
        success, msg = sender.send_email(subject, github_content, html_content)
        print(f"[GitHub] {msg}")
    else:
        print(f"[GitHub] 文件不存在: {github_file}")


def main():
    """主函数"""
    # 从环境变量读取配置
    email_config = {
        'smtp_server': os.environ.get('DIGEST_SMTP_SERVER', 'smtp.gmail.com'),
        'smtp_port': int(os.environ.get('DIGEST_SMTP_PORT', 587)),
        'sender_email': os.environ.get('DIGEST_SENDER_EMAIL'),
        'sender_password': os.environ.get('DIGEST_SENDER_PASSWORD'),
        'sender_name': os.environ.get('DIGEST_SENDER_NAME', 'Digest Bot'),
        'recipients': os.environ.get('DIGEST_RECIPIENTS', '').split(',')
    }
    
    # 检查必需配置
    if not email_config['sender_email'] or not email_config['sender_password']:
        print("错误: 请设置环境变量 DIGEST_SENDER_EMAIL 和 DIGEST_SENDER_PASSWORD")
        print("\n配置方法:")
        print("  export DIGEST_SENDER_EMAIL='your-email@gmail.com'")
        print("  export DIGEST_SENDER_PASSWORD='your-app-password'")
        print("  export DIGEST_RECIPIENTS='recipient1@example.com,recipient2@example.com'")
        sys.exit(1)
    
    if not email_config['recipients'] or not email_config['recipients'][0]:
        print("错误: 请设置环境变量 DIGEST_RECIPIENTS")
        sys.exit(1)
    
    # 发送今日日报
    send_daily_digest(email_config)


if __name__ == '__main__':
    main()
