#!/usr/bin/env python3
"""
VOXELINK GUI 服务器管理页面模块
"""

import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton, QTextEdit, QGroupBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QTimer, pyqtSignal

from .threads import ServerThread
from .utils.websocket_test import WebSocketTester


class ServerPage(QWidget):
    server_ready_changed = pyqtSignal(bool)  # 服务器就绪状态改变信号

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
        title_label = QLabel("🚀 VOXELINK 启动器")
        title_label.setObjectName("title_label")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 后端配置组
        server_group = QGroupBox("后端配置")
        server_layout = QVBoxLayout(server_group)

        # 主机和端口及按钮在一行，每部分占1/3宽度
        host_layout = QHBoxLayout()

        host_part = QHBoxLayout()
        host_part.addWidget(QLabel("主机:"))
        self.host_input = QLineEdit(self.config['gui']['server']['default_host'])
        host_part.addWidget(self.host_input)
        host_layout.addLayout(host_part, 1)

        port_part = QHBoxLayout()
        port_part.addWidget(QLabel("端口:"))
        self.port_input = QLineEdit(str(self.config['gui']['server']['default_port']))
        port_part.addWidget(self.port_input)
        host_layout.addLayout(port_part, 1)

        button_part = QHBoxLayout()
        self.toggle_button = QPushButton("▶️ 启动服务")
        self.toggle_button.setObjectName("toggle_button")
        self.toggle_button.clicked.connect(self.toggle_server)
        button_part.addWidget(self.toggle_button)
        host_layout.addLayout(button_part, 1)

        server_layout.addLayout(host_layout)

        layout.addWidget(server_group)

        # 输出区域
        output_group = QGroupBox("后端输出")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setObjectName("server_output")
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        self.output_text.setMinimumHeight(200)
        output_layout.addWidget(self.output_text)

        layout.addWidget(output_group)

    def toggle_server(self):
        if self.server_thread and self.server_thread.isRunning():
            self.stop_server()
        else:
            self.start_server()

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

        # 更新配置中的端口和WebSocket URL
        self.config['server_port'] = port_int
        self.config['gui']['server']['realtime_chat_ws_url'] = f"ws://localhost:{port}/ws/realtime_chat"
        self.config['gui']['server']['stt_ws_url'] = f"ws://localhost:{port}/stt/ws"

        self.output_text.clear()

        self.server_thread = ServerThread(host, port_int, enable_stt, enable_tts)
        self.server_thread.output_signal.connect(self.append_output)
        self.server_thread.finished_signal.connect(self.on_server_finished)
        self.server_thread.start()

        self.toggle_button.setText("⏹️ 停止服务")
        self.server_ready = False
        self.server_ready_changed.emit(False)


    def stop_server(self):
        # 重置服务器状态
        self.server_ready = False
        self.server_ready_changed.emit(False)
        # 清理WebSocket测试资源
        if self.websocket_tester:
            self.websocket_tester.cleanup()
            self.websocket_tester = None

        if self.server_thread:
            self.server_thread.stop()
        self.toggle_button.setText("▶️ 启动服务")

    def append_output(self, text):
        # 过滤ANSI转义序列（颜色代码等）
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[mG]')
        clean_text = ansi_escape.sub('', text)
        self.output_text.append(clean_text)

        # 检测服务器是否已启动完成
        if "Uvicorn running on" in clean_text:
            self.output_text.append("🎯 检测到后端服务启动完成")
            # 延迟2秒后开始WebSocket测试，确保服务完全可用
            QTimer.singleShot(2000, self.start_websocket_test)

    def on_server_finished(self):
        self.server_ready = False
        self.server_ready_changed.emit(False)
        self.toggle_button.setText("▶️ 启动服务")

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
            self.server_ready = True
            self.server_ready_changed.emit(True)
            self.output_text.append("✅ " + message)
            self.output_text.append("📝 服务启动正常")
        else:
            self.server_ready = False
            self.server_ready_changed.emit(False)
            self.output_text.append("❌ " + message)