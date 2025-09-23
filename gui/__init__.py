#!/usr/bin/env python3
"""
VOXELINK GUI 应用入口

启动GUI应用程序。
"""

import sys
from PyQt6.QtWidgets import QApplication

from .main_window import VoxelinkGUI


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 使用现代风格

    # 设置应用程序图标 (如果有的话)
    # app.setWindowIcon(QIcon("icon.png"))

    window = VoxelinkGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()