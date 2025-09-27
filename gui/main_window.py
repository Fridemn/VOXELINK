#!/usr/bin/env python3
"""
VOXELINK GUI 主窗口模块

包含主要的GUI窗口类和相关功能。
"""

from PyQt6.QtWidgets import QApplication, QMainWindow, QSplitter, QListWidget, QListWidgetItem, QStackedWidget, QMenuBar, QMenu
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtCore import Qt

from .server_page import ServerPage
from .realtime_chat_page import RealtimeChatPage
from .config_page import ConfigPage
from .history_page import HistoryPage
from .live2d_desktop_pet import start_desktop_pet
from .modern_styles import style_manager

# 导入配置
from backend.app.config.app_config import AppConfig


class VoxelinkGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化配置
        self.config = AppConfig()
        self.current_theme = 'custom_dark'

        # 初始化页面
        self.server_page = ServerPage(self.config)
        self.realtime_chat_page = RealtimeChatPage(self.config)
        self.config_page = ConfigPage(self.config)
        self.history_page = HistoryPage(self.config)

        self.init_ui()
        self.setup_menu_bar()

        # 连接服务器状态信号
        self.server_page.server_ready_changed.connect(self.update_status_bar)

    def init_ui(self):
        self.setWindowTitle("🎤 VOXELINK 启动器")
        self.setGeometry(200, 200, 1200, 800)
        self.setMinimumSize(1000, 600)

        # 设置字体
        font = QFont("Segoe UI", 10)
        self.setFont(font)
        
        # 设置窗口属性
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # 创建主分割器
        main_splitter = QSplitter()
        self.setCentralWidget(main_splitter)

        # 左侧导航栏
        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(180)
        self.nav_list.setMinimumWidth(160)
        self.nav_list.setObjectName("navigation_list")

        # 添加导航项
        server_item = QListWidgetItem("🚀 启动管理")
        server_item.setFont(QFont("Segoe UI", 11))
        self.nav_list.addItem(server_item)

        realtime_chat_item = QListWidgetItem("🔄 实时语音聊天")
        realtime_chat_item.setFont(QFont("Segoe UI", 11))
        self.nav_list.addItem(realtime_chat_item)

        history_item = QListWidgetItem("💬 历史记录")
        history_item.setFont(QFont("Segoe UI", 11))
        self.nav_list.addItem(history_item)

        config_item = QListWidgetItem("⚙️ 配置文件管理")
        config_item.setFont(QFont("Segoe UI", 11))
        self.nav_list.addItem(config_item)

        self.nav_list.currentRowChanged.connect(self.change_page)
        main_splitter.addWidget(self.nav_list)

        # 右侧内容区域
        self.stacked_widget = QStackedWidget()
        main_splitter.addWidget(self.stacked_widget)

        # 设置分割器比例
        main_splitter.setSizes([180, 1020])
        main_splitter.setChildrenCollapsible(False)

        # 添加页面到堆栈
        self.stacked_widget.addWidget(self.server_page)
        self.stacked_widget.addWidget(self.realtime_chat_page)
        self.stacked_widget.addWidget(self.history_page)
        self.stacked_widget.addWidget(self.config_page)

        # 设置默认页面
        self.nav_list.setCurrentRow(0)

        # 状态栏
        self.statusBar().showMessage("服务未启动")

        # 启动Live2D桌宠
        self.desktop_pet = start_desktop_pet(self.config)

    def setup_menu_bar(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 视图菜单
        view_menu = menubar.addMenu('视图(&V)')
        
        # 主题子菜单
        theme_menu = view_menu.addMenu('🎨 主题')
        
        # 获取可用主题
        themes = style_manager.get_available_themes()
        
        # 添加主题选项
        for theme in themes:
            theme_action = QAction(self.get_theme_display_name(theme), self)
            theme_action.setCheckable(True)
            theme_action.setChecked(theme == self.current_theme)
            theme_action.triggered.connect(lambda checked, t=theme: self.change_theme(t))
            theme_menu.addAction(theme_action)
        
        # 全屏切换
        fullscreen_action = QAction('全屏(&F)', self)
        fullscreen_action.setShortcut('F11')
        fullscreen_action.setCheckable(True)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助(&H)')

        
        # 文档
        docs_action = QAction('文档(&D)', self)
        docs_action.triggered.connect(self.show_docs)
        help_menu.addAction(docs_action)
        
        # 反馈
        feedback_action = QAction('反馈(&F)', self)
        feedback_action.triggered.connect(self.show_feedback)
        help_menu.addAction(feedback_action)
    
    def get_theme_display_name(self, theme):
        """获取主题显示名称"""
        theme_names = {
            'custom_dark': '🌙 自定义深色',
            'qtmodern_dark': '🔷 现代深色',
            'dark_teal.xml': '🟢 深色青色',
            'dark_blue.xml': '🔵 深色蓝色',
            'dark_amber.xml': '🟡 深色琥珀',
            'dark_cyan.xml': '🟦 深色青蓝',
            'dark_lightgreen.xml': '🟢 深色浅绿',
            'dark_pink.xml': '🩷 深色粉色',
            'dark_purple.xml': '🟣 深色紫色',
            'dark_red.xml': '🔴 深色红色',
            'dark_yellow.xml': '🟡 深色黄色',
            'light_teal.xml': '🟢 浅色青色',
            'light_blue.xml': '🔵 浅色蓝色',
            'light_amber.xml': '🟡 浅色琥珀',
            'light_cyan.xml': '🟦 浅色青蓝',
            'light_lightgreen.xml': '🟢 浅色浅绿',
            'light_pink.xml': '🩷 浅色粉色',
            'light_purple.xml': '🟣 浅色紫色',
            'light_red.xml': '🔴 浅色红色',
            'light_yellow.xml': '🟡 浅色黄色'
        }
        return theme_names.get(theme, theme)
    
    def change_theme(self, theme_name):
        """切换主题"""
        if theme_name != self.current_theme:
            self.current_theme = theme_name
            app = QApplication.instance()
            style_manager.apply_theme(app, self, theme_name)
            
            # 更新菜单中的选中状态
            menubar = self.menuBar()
            for menu in menubar.findChildren(QMenu):
                if menu.title() == '🎨 主题':
                    for action in menu.actions():
                        action.setChecked(self.get_theme_display_name(theme_name) == action.text())
    
    def toggle_fullscreen(self):
        """切换全屏模式"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def show_docs(self):
        """显示文档"""
        import webbrowser
        # 假设文档URL，实际应替换为真实URL
        docs_url = "https://github.com/Fridemn/VOXELINK"
        webbrowser.open(docs_url)
    
    def show_feedback(self):
        """显示反馈"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, '反馈', 
                               '请通过以下方式提供反馈：\n\n'
                               'GitHub Issues: https://github.com/Fridemn/VOXELINK/issues\n'
                               '邮箱: fridemn@qq.com')


    def change_page(self, index):
        self.stacked_widget.setCurrentIndex(index)

    def update_status_bar(self, ready):
        """更新状态栏消息"""
        if ready:
            self.statusBar().showMessage("就绪")
        else:
            self.statusBar().showMessage("服务未启动")

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止服务器
        if self.server_page.server_thread and self.server_page.server_thread.isRunning():
            self.server_page.stop_server()

        # 断开所有连接
        self.realtime_chat_page.disconnect()

        if hasattr(self, 'desktop_pet') and self.desktop_pet:
            self.desktop_pet.close()

        QApplication.quit()

        event.accept()
