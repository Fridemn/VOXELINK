#!/usr/bin/env python3
"""
VOXELINK GUI 应用入口

启动GUI应用程序。
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .main_window import VoxelinkGUI
from .modern_styles import style_manager


def main():
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except AttributeError:
        pass
    
    app = QApplication(sys.argv)
    try:
        app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except AttributeError:
        pass
    
    # 设置应用程序信息
    app.setApplicationName("VOXELINK")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("Fridemn")
    
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)
    
    window = VoxelinkGUI()
    
    styled_window = style_manager.apply_theme(app, window, 'custom_dark')
    
    if styled_window != window:
        styled_window.show()
    else:
        window.show()
    
    # 设置应用程序图标 (如果有的话)
    # app.setWindowIcon(QIcon("icon.png"))
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()