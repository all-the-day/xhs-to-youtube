#!/bin/bash
#
# 小红书到YouTube视频搬运工具 - 环境配置脚本
# 
# 使用方法: bash setup.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "小红书 → YouTube 视频搬运工具 - 环境配置"
echo "=================================================="

# 检查 Python 版本
echo ""
echo "[1/4] 检查 Python 环境..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "    ✓ 找到 $PYTHON_VERSION"
else
    echo "    ✗ 未找到 Python3，请先安装 Python 3.8+"
    exit 1
fi

# 安装依赖
echo ""
echo "[2/4] 安装 Python 依赖..."
if command -v pip3 &> /dev/null; then
    pip3 install yt-dlp google-api-python-client google-auth-oauthlib google-auth-httplib2 gradio --quiet
    echo "    ✓ 依赖安装完成"
elif python3 -m pip --version &> /dev/null; then
    python3 -m pip install yt-dlp google-api-python-client google-auth-oauthlib google-auth-httplib2 gradio --quiet
    echo "    ✓ 依赖安装完成"
else
    echo "    ⚠ 未找到 pip，请手动安装:"
    echo ""
    echo "    # Ubuntu/Debian:"
    echo "    sudo apt-get update && sudo apt-get install -y python3-pip"
    echo ""
    echo "    # 或使用 get-pip.py:"
    echo "    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py"
    echo "    python3 get-pip.py"
    echo ""
    echo "    然后运行以下命令安装依赖:"
    echo "    pip3 install yt-dlp google-api-python-client google-auth-oauthlib google-auth-httplib2 gradio"
    echo ""
    exit 1
fi

# 创建必要的文件占位符
echo ""
echo "[3/4] 创建配置文件..."

# 创建 cookies.txt 占位符
if [ ! -f "cookies.txt" ]; then
    echo "# 小红书 Cookie 文件" > cookies.txt
    echo "# 请按照 SETUP_GUIDE.md 中的说明导出 Cookie" >> cookies.txt
    echo "    ✓ 已创建 cookies.txt 占位符"
else
    echo "    ✓ cookies.txt 已存在"
fi

# 创建 videos 目录
mkdir -p videos
echo "    ✓ videos/ 目录已创建"

echo ""
echo "[4/4] 检查凭证文件..."
if [ -f "credentials.json" ]; then
    echo "    ✓ credentials.json 已存在"
else
    echo "    ⚠ credentials.json 不存在"
    echo ""
    echo "=================================================="
    echo "请按照以下步骤获取 Google Cloud 凭证:"
    echo "=================================================="
    echo ""
    echo "1. 访问 Google Cloud Console:"
    echo "   https://console.cloud.google.com/"
    echo ""
    echo "2. 创建新项目:"
    echo "   - 点击顶部项目选择器"
    echo "   - 点击 '新建项目'"
    echo "   - 输入项目名称（如: xhs-to-youtube）"
    echo "   - 点击 '创建'"
    echo ""
    echo "3. 启用 YouTube Data API:"
    echo "   - 在搜索框输入 'YouTube Data API v3'"
    echo "   - 点击进入，然后点击 '启用'"
    echo ""
    echo "4. 配置 OAuth 同意屏幕:"
    echo "   - 左侧菜单: API和服务 → OAuth 同意屏幕"
    echo "   - 选择 '外部' 用户类型"
    echo "   - 填写应用名称（如: XHS to YouTube）"
    echo "   - 填写开发者邮箱"
    echo "   - 点击 '保存并继续'"
    echo "   - 作用域页面直接点击 '保存并继续'"
    echo "   - 测试用户页面添加你自己的 Google 邮箱"
    echo ""
    echo "5. 创建 OAuth 凭证:"
    echo "   - 左侧菜单: API和服务 → 凭证"
    echo "   - 点击 '创建凭证' → 'OAuth 客户端 ID'"
    echo "   - 应用类型选择 '桌面应用'"
    echo "   - 输入名称（如: XHS Uploader）"
    echo "   - 点击 '创建'"
    echo "   - 点击下载 JSON 图标"
    echo "   - 将下载的文件保存为:"
    echo "     $SCRIPT_DIR/credentials.json"
    echo ""
fi

echo ""
echo "=================================================="
echo "配置完成检查清单:"
echo "=================================================="
echo ""

# 检查 cookies.txt
if [ -f "cookies.txt" ] && [ -s "cookies.txt" ]; then
    if grep -q "请按照" cookies.txt 2>/dev/null; then
        echo "[ ] cookies.txt - 需要导入小红书 Cookie"
    else
        echo "[✓] cookies.txt - 已配置"
    fi
else
    echo "[ ] cookies.txt - 需要导入小红书 Cookie"
fi

# 检查 credentials.json
if [ -f "credentials.json" ]; then
    echo "[✓] credentials.json - 已配置"
else
    echo "[ ] credentials.json - 需要从 Google Cloud Console 下载"
fi

echo ""
echo "=================================================="
echo "导出小红书 Cookie 的方法:"
echo "=================================================="
echo ""
echo "方法一：使用浏览器扩展（推荐）"
echo "  1. 安装 Chrome 扩展: 'EditThisCookie' 或 'Cookie Editor'"
echo "  2. 登录小红书网页版: https://www.xiaohongshu.com"
echo "  3. 点击扩展图标，导出 Cookie 为 Netscape 格式"
echo "  4. 保存到: $SCRIPT_DIR/cookies.txt"
echo ""
echo "方法二：使用 yt-dlp 自动提取"
echo "  如果使用 Chrome 登录了小红书，可以运行:"
echo "  yt-dlp --cookies-from-browser chrome <URL>"
echo "  但建议手动导出以获得更稳定的 Cookie"
echo ""
echo "方法三：手动复制（高级）"
echo "  1. 打开 Chrome 开发者工具 (F12)"
echo "  2. 切换到 Network 标签"
echo "  3. 刷新小红书页面"
echo "  4. 找到任意请求，查看 Request Headers 中的 Cookie"
echo "  5. 格式化成 Netscape 格式保存"
echo ""
echo "=================================================="
echo "完成以上配置后，使用以下命令搬运视频:"
echo "=================================================="
echo ""
echo "  python main.py \"小红书视频URL\" --title-en \"英文标题\""
echo ""
