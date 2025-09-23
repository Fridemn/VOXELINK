#!/usr/bin/env python3
"""
VOXELINK GUI 启动器

使用 PyQt6 创建的桌面 GUI，用于启动 VOXELINK 后端服务。
"""

import sys
from pathlib import Path

# 添加backend目录到Python路径
backend_dir = Path(__file__).parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 添加backend/app目录到Python路径
app_dir = backend_dir / "app"
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from gui import main

if __name__ == "__main__":
    main()
