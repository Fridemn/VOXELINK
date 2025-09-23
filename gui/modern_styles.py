#!/usr/bin/env python3
"""
VOXELINK GUI 现代化样式模块

使用 qtmodern 和 qt-material 提供现代化的GUI样式
"""

import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPalette, QColor

# 尝试导入qtmodern和qt-material
try:
    import qtmodern.styles
    import qtmodern.windows
    QTMODERN_AVAILABLE = True
except ImportError:
    QTMODERN_AVAILABLE = False
    print("qtmodern 未安装，将使用内置样式")

try:
    from qt_material import apply_stylesheet
    QT_MATERIAL_AVAILABLE = True
except ImportError:
    QT_MATERIAL_AVAILABLE = False
    print("qt-material 未安装，将使用内置样式")


class ModernStyleManager:
    """现代化样式管理器"""
    
    def __init__(self):
        self.current_theme = "dark"
        
    def apply_qtmodern_style(self, app, window):
        """应用qtmodern样式"""
        if QTMODERN_AVAILABLE:
            qtmodern.styles.dark(app)
            return qtmodern.windows.ModernWindow(window)
        return window
    
    def apply_qt_material_style(self, app, theme="dark_teal.xml"):
        """应用qt-material样式"""
        if QT_MATERIAL_AVAILABLE:
            apply_stylesheet(app, theme=theme)
            return True
        return False
    
    def apply_custom_dark_style(self, app):
        """应用自定义深色样式"""
        dark_style = """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 10pt;
        }
        
        /* 导航列表样式 */
        QListWidget {
            background-color: #1e1e1e;
            border: 1px solid #404040;
            border-radius: 8px;
            padding: 5px;
            outline: none;
        }
        
        QListWidget::item {
            background-color: transparent;
            color: #ffffff;
            padding: 12px 8px;
            margin: 2px 0px;
            border-radius: 6px;
            border: none;
        }
        
        QListWidget::item:selected {
            background-color: #0078d4;
            color: #ffffff;
        }
        
        QListWidget::item:hover {
            background-color: #404040;
        }
        
        /* 按钮样式 */
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-weight: bold;
            min-width: 80px;
        }
        
        QPushButton:hover {
            background-color: #106ebe;
        }
        
        QPushButton:pressed {
            background-color: #005a9e;
        }
        
        QPushButton:disabled {
            background-color: #404040;
            color: #808080;
        }
        
        /* 特殊按钮样式 */
        QPushButton#start_button {
            background-color: #107c10;
        }
        
        QPushButton#start_button:hover {
            background-color: #0e6e0e;
        }
        
        QPushButton#stop_button {
            background-color: #d13438;
        }
        
        QPushButton#stop_button:hover {
            background-color: #b92b2f;
        }
        
        QPushButton#connect_button {
            background-color: #0078d4;
        }
        
        QPushButton#disconnect_button {
            background-color: #d13438;
        }
        
        /* 输入框样式 */
        QLineEdit {
            background-color: #404040;
            border: 1px solid #606060;
            border-radius: 4px;
            padding: 8px;
            color: #ffffff;
        }
        
        QLineEdit:focus {
            border: 2px solid #0078d4;
        }
        
        /* 文本编辑器样式 */
        QTextEdit, QTextBrowser {
            background-color: #1e1e1e;
            border: 1px solid #404040;
            border-radius: 6px;
            padding: 8px;
            color: #ffffff;
            font-family: 'Consolas', 'Courier New', monospace;
        }
        
        /* 复选框样式 */
        QCheckBox {
            color: #ffffff;
            padding: 5px;
        }
        
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
        }
        
        QCheckBox::indicator:unchecked {
            background-color: #404040;
            border: 2px solid #606060;
            border-radius: 3px;
        }
        
        QCheckBox::indicator:checked {
            background-color: #0078d4;
            border: 2px solid #0078d4;
            border-radius: 3px;
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUwzLjUgN0wxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
        }
        
        QCheckBox::indicator:hover {
            border: 2px solid #0078d4;
        }
        
        /* 组框样式 */
        QGroupBox {
            font-weight: bold;
            border: 2px solid #404040;
            border-radius: 8px;
            margin: 10px 0px;
            padding-top: 10px;
            color: #ffffff;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 8px 0 8px;
            color: #0078d4;
            font-weight: bold;
        }
        
        /* 标签样式 */
        QLabel {
            color: #ffffff;
        }
        
        QLabel#title_label {
            color: #0078d4;
            font-size: 16pt;
            font-weight: bold;
            margin: 10px 0px;
        }
        
        QLabel#status_connected {
            color: #107c10;
            font-weight: bold;
        }
        
        QLabel#status_connected {
            color: #107c10;
            font-weight: bold;
        }
        
        QLabel#status_disconnected {
            color: #d13438;
            font-weight: bold;
        }
        
        QLabel#status_connecting {
            color: #ff8c00;
            font-weight: bold;
        }
        
        /* 进度条样式 */
        QProgressBar {
            border: 1px solid #404040;
            border-radius: 6px;
            background-color: #1e1e1e;
            text-align: center;
            color: #ffffff;
        }
        
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 5px;
        }
        
        /* 滚动条样式 */
        QScrollBar:vertical {
            background-color: #2b2b2b;
            width: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:vertical {
            background-color: #606060;
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #808080;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
        }
        
        /* 状态栏样式 */
        QStatusBar {
            background-color: #1e1e1e;
            color: #ffffff;
            border-top: 1px solid #404040;
        }
        
        /* 分割器样式 */
        QSplitter::handle {
            background-color: #404040;
        }
        
        QSplitter::handle:horizontal {
            width: 3px;
        }
        
        QSplitter::handle:vertical {
            height: 3px;
        }
        
        /* 下拉框样式 */
        QComboBox {
            background-color: #404040;
            border: 1px solid #606060;
            border-radius: 4px;
            padding: 8px;
            color: #ffffff;
            min-width: 100px;
        }
        
        QComboBox:hover {
            border: 2px solid #0078d4;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        
        QComboBox::down-arrow {
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDFMNiA2TDExIDEiIHN0cm9rZT0iI2ZmZmZmZiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPHN2Zz4K);
            width: 12px;
            height: 8px;
        }
        
        QComboBox QAbstractItemView {
            background-color: #404040;
            border: 1px solid #606060;
            selection-background-color: #0078d4;
            color: #ffffff;
        }
        
        /* 数字输入框样式 */
        QSpinBox, QDoubleSpinBox {
            background-color: #404040;
            border: 1px solid #606060;
            border-radius: 4px;
            padding: 8px;
            color: #ffffff;
        }
        
        QSpinBox:focus, QDoubleSpinBox:focus {
            border: 2px solid #0078d4;
        }
        
        QSpinBox::up-button, QDoubleSpinBox::up-button {
            background-color: #606060;
            border: none;
            border-top-right-radius: 4px;
        }
        
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            background-color: #606060;
            border: none;
            border-bottom-right-radius: 4px;
        }
        
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
            background-color: #0078d4;
        }
        """
        
        app.setStyleSheet(dark_style)
        
        # 设置应用程序调色板
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(43, 43, 43))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(64, 64, 64))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Button, QColor(64, 64, 64))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        
        app.setPalette(palette)
    
    def get_available_themes(self):
        """获取可用的主题列表"""
        themes = ['custom_dark']
        
        if QT_MATERIAL_AVAILABLE:
            themes.extend([
                'dark_teal.xml',
                'dark_blue.xml', 
                'dark_amber.xml',
                'dark_cyan.xml',
                'dark_lightgreen.xml',
                'dark_pink.xml',
                'dark_purple.xml',
                'dark_red.xml',
                'dark_yellow.xml',
                'light_teal.xml',
                'light_blue.xml',
                'light_amber.xml',
                'light_cyan.xml',
                'light_lightgreen.xml',
                'light_pink.xml',
                'light_purple.xml',
                'light_red.xml',
                'light_yellow.xml'
            ])
        
        return themes
    
    def apply_theme(self, app, window, theme_name):
        """应用指定主题"""
        if theme_name == 'custom_dark':
            self.apply_custom_dark_style(app)
            return window
        elif theme_name == 'qtmodern_dark' and QTMODERN_AVAILABLE:
            return self.apply_qtmodern_style(app, window)
        elif theme_name.endswith('.xml') and QT_MATERIAL_AVAILABLE:
            self.apply_qt_material_style(app, theme_name)
            return window
        else:
            # 默认使用自定义深色主题
            self.apply_custom_dark_style(app)
            return window


# 全局样式管理器实例
style_manager = ModernStyleManager()