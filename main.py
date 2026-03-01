#!/usr/bin/env python3
"""
小红书视频搬运到 YouTube 的自动化脚本

这是兼容旧入口的包装器，新代码请使用:
    python -m src.cli -i    # 交互式模式
    python -m src.cli --help  # 查看帮助
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.cli import main

if __name__ == "__main__":
    main()