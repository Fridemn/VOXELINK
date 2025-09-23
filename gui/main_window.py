#!/usr/bin/env python3
"""
VOXELINK GUI 主窗口模块

包含主要的GUI窗口类和相关功能。
"""

from PyQt6.QtWidgets import QApplication, QMainWindow, QSplitter, QListWidget, QListWidgetItem, QStackedWidget
from PyQt6.QtGui import QFont

from .server_page import ServerPage
from .realtime_chat_page import RealtimeChatPage
from .config_page import ConfigPage

# 导入配置
from backend.app.config.app_config import AppConfig


class VoxelinkGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化配置
        self.config = AppConfig()

        # 初始化页面
        self.server_page = ServerPage(self.config)
        self.realtime_chat_page = RealtimeChatPage(self.config)
        self.config_page = ConfigPage(self.config)

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("VOXELINK 启动器")
        self.setGeometry(300, 300, 1000, 600)

        # 设置字体
        font = QFont("Arial", 10)
        self.setFont(font)

        # 创建主分割器
        main_splitter = QSplitter()
        self.setCentralWidget(main_splitter)

        # 左侧导航栏
        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(150)
        self.nav_list.setMinimumWidth(120)

        # 添加导航项
        server_item = QListWidgetItem(" 启动管理")
        server_item.setFont(QFont("Arial", 11))
        self.nav_list.addItem(server_item)

        realtime_chat_item = QListWidgetItem(" 实时语音聊天")
        realtime_chat_item.setFont(QFont("Arial", 11))
        self.nav_list.addItem(realtime_chat_item)

        config_item = QListWidgetItem(" 配置文件管理")
        config_item.setFont(QFont("Arial", 11))
        self.nav_list.addItem(config_item)

        self.nav_list.currentRowChanged.connect(self.change_page)
        main_splitter.addWidget(self.nav_list)

        # 右侧内容区域
        self.stacked_widget = QStackedWidget()
        main_splitter.addWidget(self.stacked_widget)

        # 设置分割器比例
        main_splitter.setSizes([150, 850])

        # 添加页面到堆栈
        self.stacked_widget.addWidget(self.server_page)
        self.stacked_widget.addWidget(self.realtime_chat_page)
        self.stacked_widget.addWidget(self.config_page)

        # 设置默认页面
        self.nav_list.setCurrentRow(0)

        # 状态栏
        self.statusBar().showMessage("就绪")

    def change_page(self, index):
        self.stacked_widget.setCurrentIndex(index)

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止服务器
        if self.server_page.server_thread and self.server_page.server_thread.isRunning():
            self.server_page.stop_server()

        # 断开所有连接
        self.realtime_chat_page.disconnect()

        event.accept()
