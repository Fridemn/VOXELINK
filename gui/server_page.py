#!/usr/bin/env python3
"""
VOXELINK GUI 服务器管理页面模块
"""

import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton, QTextEdit, QGroupBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QTimer

from .threads import ServerThread
from .utils.websocket_test import WebSocketTester


class ServerPage(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.server_thread = None
        self.websocket_tester = None
        self.server_ready = False  # 标记服务器是否已准备就绪
        self.init_ui()

    def __del__(self):
        """析构函数，确保资源被正确清理"""
        try:
            if self.websocket_tester:
                self.websocket_tester.cleanup()
        except:
            pass

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("🚀 VOXELINK 后端服务启动器")
        title_label.setObjectName("title_label")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 服务器配置组
        server_group = QGroupBox("服务器配置")
        server_layout = QVBoxLayout(server_group)

        # 主机和端口
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("主机:"))
        self.host_input = QLineEdit(self.config['gui']['server']['default_host'])
        host_layout.addWidget(self.host_input)
        host_layout.addWidget(QLabel("端口:"))
        self.port_input = QLineEdit(str(self.config['gui']['server']['default_port']))
        host_layout.addWidget(self.port_input)
        server_layout.addLayout(host_layout)

        layout.addWidget(server_group)

        # 控制按钮
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("▶️ 启动服务")
        self.start_button.setObjectName("start_button")
        self.start_button.clicked.connect(self.start_server)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("⏹️ 停止服务")
        self.stop_button.setObjectName("stop_button")
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        layout.addLayout(button_layout)

        # 输出区域
        output_group = QGroupBox("服务器输出")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setObjectName("server_output")
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        self.output_text.setMinimumHeight(200)
        output_layout.addWidget(self.output_text)

        layout.addWidget(output_group)

    def start_server(self):
        if self.server_thread and self.server_thread.isRunning():
            self.output_text.append("⚠️ 服务器已在运行")
            return

        host = self.host_input.text()
        port = self.port_input.text()
        enable_stt = True
        enable_tts = True

        try:
            port_int = int(port)
        except ValueError:
            self.output_text.append("❌ 端口必须是数字")
            return

        self.output_text.clear()
        self.output_text.append("🚀 启动 VOXELINK 后端服务...")
        self.output_text.append(f"📍 主机: {host}")
        self.output_text.append(f"🔌 端口: {port_int}")

        services = ["后端", "STT", "TTS"]
        self.output_text.append(f"📦 启用的服务: {', '.join(services)}")

        self.server_thread = ServerThread(host, port_int, enable_stt, enable_tts)
        self.server_thread.output_signal.connect(self.append_output)
        self.server_thread.finished_signal.connect(self.on_server_finished)
        self.server_thread.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.server_ready = False

        # 不再使用固定延时，而是通过监听服务器输出来判断启动完成

    def stop_server(self):
        # 重置服务器状态
        self.server_ready = False
        # 清理WebSocket测试资源
        if self.websocket_tester:
            self.websocket_tester.cleanup()
            self.websocket_tester = None

        if self.server_thread:
            self.server_thread.stop()
            self.server_thread.wait(5000)
            self.on_server_finished()

    def append_output(self, text):
        # 过滤ANSI转义序列（颜色代码等）
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[mG]')
        clean_text = ansi_escape.sub('', text)
        self.output_text.append(clean_text)

        # 检测服务器是否已启动完成
        if not self.server_ready and "Uvicorn running on" in clean_text:
            self.server_ready = True
            self.output_text.append("🎯 检测到后端服务启动完成")
            # 延迟2秒后开始WebSocket测试，确保服务完全可用
            QTimer.singleShot(2000, self.start_websocket_test)

    def on_server_finished(self):
        self.server_ready = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def start_websocket_test(self):
        """开始WebSocket连接测试"""
        try:
            # 清理之前的测试器
            if self.websocket_tester:
                self.websocket_tester.cleanup()
                self.websocket_tester = None

            self.output_text.append("🔍 开始WebSocket连接测试...")

            url = self.config['gui']['server']['realtime_chat_ws_url']
            self.output_text.append(f"📡 连接到: {url}")

            self.websocket_tester = WebSocketTester(url)
            self.websocket_tester.test_completed.connect(self.on_websocket_test_completed)
            self.websocket_tester.start_test()

        except Exception as e:
            self.output_text.append(f"❌ WebSocket测试初始化失败: {str(e)}")

    def on_websocket_test_completed(self, success, message):
        """WebSocket测试完成回调"""
        if success:
            self.output_text.append("✅ " + message)
            self.output_text.append("📝 服务启动正常")
        else:
            self.output_text.append("❌ " + message)