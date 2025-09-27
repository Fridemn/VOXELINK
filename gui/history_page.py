#!/usr/bin/env python3
"""
VOXELINK GUI 历史记录页面模块

显示用户和LLM的对话历史记录，模仿微信风格。
"""

import json
import requests
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTextEdit, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QBrush


class HistoryPage(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.backend_url = f"http://localhost:{self.config.get('server_port', 8080)}"
        self.history_data = []

        self.init_ui()
        # 移除自动加载历史记录

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 标题和刷新按钮
        header_layout = QHBoxLayout()

        title_label = QLabel("💬 对话历史记录")
        title_label.setObjectName("title_label")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.load_history)
        header_layout.addWidget(refresh_btn)

        # 清除按钮
        clear_btn = QPushButton("🗑️ 清除历史")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4757;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff3742;
            }
        """)
        clear_btn.clicked.connect(self.clear_history)
        header_layout.addWidget(clear_btn)

        layout.addLayout(header_layout)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # 消息容器
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setSpacing(10)
        self.messages_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_area.setWidget(self.messages_widget)
        layout.addWidget(self.scroll_area)

        # 加载指示器
        self.loading_label = QLabel("正在加载历史记录...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.loading_label)
        self.loading_label.hide()

    def load_history(self):
        """加载历史记录"""
        self.loading_label.show()

        # 在后台线程中加载
        self.history_thread = HistoryLoaderThread(self.backend_url)
        self.history_thread.finished.connect(self.on_history_loaded)
        self.history_thread.error.connect(self.on_history_error)
        self.history_thread.start()

    def on_history_loaded(self, history_data):
        """历史记录加载完成"""
        self.loading_label.hide()
        self.history_data = history_data
        self.display_messages()

    def on_history_error(self, error_msg):
        """历史记录加载失败"""
        self.loading_label.hide()
        QMessageBox.warning(self, "加载失败", f"无法加载历史记录：{error_msg}")

    def display_messages(self):
        """显示消息列表"""
        # 清空现有消息
        while self.messages_layout.count():
            child = self.messages_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.history_data:
            no_history_label = QLabel("暂无对话历史记录")
            no_history_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_history_label.setStyleSheet("color: #666; font-style: italic; padding: 20px;")
            self.messages_layout.addWidget(no_history_label)
            return

        # 显示消息
        for msg_data in self.history_data:
            message_widget = self.create_message_widget(msg_data)
            self.messages_layout.addWidget(message_widget)

        # 添加底部间距
        self.messages_layout.addStretch()

        # 滚动到底部
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def create_message_widget(self, msg_data):
        """创建消息气泡组件"""
        # 解析消息数据
        sender = msg_data.get('sender', {})
        role = sender.get('role', 'user')
        nickname = sender.get('nickname', 'Unknown')
        content = msg_data.get('message_str', '')
        timestamp = msg_data.get('timestamp', 0)

        # 创建消息容器
        message_container = QWidget()
        message_layout = QHBoxLayout(message_container)
        message_layout.setContentsMargins(0, 0, 0, 0)

        if role == 'user':
            # 用户消息（右对齐）
            message_layout.addStretch()

            # 消息气泡
            bubble_widget = self.create_message_bubble(content, timestamp, is_user=True)
            message_layout.addWidget(bubble_widget)

            # 用户头像
            avatar_label = self.create_avatar("👤", is_user=True)
            message_layout.addWidget(avatar_label)
        else:
            # LLM消息（左对齐）
            # LLM头像
            avatar_label = self.create_avatar("🤖", is_user=False)
            message_layout.addWidget(avatar_label)

            # 消息气泡
            bubble_widget = self.create_message_bubble(content, timestamp, is_user=False)
            message_layout.addWidget(bubble_widget)

            message_layout.addStretch()

        return message_container

    def create_message_bubble(self, content, timestamp, is_user=True):
        """创建消息气泡"""
        bubble_widget = QWidget()
        bubble_layout = QVBoxLayout(bubble_widget)
        bubble_layout.setContentsMargins(10, 5, 10, 5)

        # 消息内容
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setMaximumWidth(400)
        content_label.setStyleSheet(f"""
            QLabel {{
                color: {'white' if is_user else 'black'};
                padding: 8px 12px;
                border-radius: 12px;
                background-color: {'#007AFF' if is_user else '#E5E5EA'};
                font-size: 14px;
                line-height: 1.4;
            }}
        """)

        bubble_layout.addWidget(content_label)

        # 时间戳
        from datetime import datetime
        time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M")
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #666; font-size: 10px; margin-top: 2px;")
        time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble_layout.addWidget(time_label)

        return bubble_widget

    def create_avatar(self, emoji, is_user=True):
        """创建头像"""
        avatar_label = QLabel(emoji)
        avatar_label.setFixedSize(40, 40)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_label.setStyleSheet(f"""
            QLabel {{
                border-radius: 20px;
                background-color: {'#007AFF' if is_user else '#34C759'};
                color: white;
                font-size: 18px;
                font-weight: bold;
            }}
        """)
        return avatar_label

    def clear_history(self):
        """清除历史记录"""
        reply = QMessageBox.question(
            self, "确认清除",
            "确定要清除所有对话历史记录吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                response = requests.delete(f"{self.backend_url}/llm/history", timeout=10)
                if response.status_code == 200:
                    QMessageBox.information(self, "成功", "历史记录已清除")
                    self.history_data = []
                    self.display_messages()
                else:
                    QMessageBox.warning(self, "失败", f"清除失败：{response.text}")
            except Exception as e:
                QMessageBox.warning(self, "失败", f"清除失败：{str(e)}")


class HistoryLoaderThread(QThread):
    """历史记录加载线程"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, backend_url):
        super().__init__()
        self.backend_url = backend_url

    def run(self):
        try:
            response = requests.get(f"{self.backend_url}/llm/history/messages", timeout=10)
            if response.status_code == 200:
                data = response.json()
                messages = data.get('messages', [])
                self.finished.emit(messages)
            else:
                self.error.emit(f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            self.error.emit(str(e))