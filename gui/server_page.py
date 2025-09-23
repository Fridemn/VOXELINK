#!/usr/bin/env python3
"""
VOXELINK GUI 服务器管理页面模块
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton, QTextEdit, QGroupBox
from PyQt6.QtGui import QFont

from .threads import ServerThread


class ServerPage(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.server_thread = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("🚀 VOXELINK 后端服务启动器")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 服务配置组
        config_group = QGroupBox("服务配置")
        config_layout = QVBoxLayout(config_group)

        # STT 和 TTS 复选框
        self.stt_checkbox = QCheckBox("启用语音识别 (STT) 服务")
        self.tts_checkbox = QCheckBox("启用语音合成 (TTS) 服务")
        config_layout.addWidget(self.stt_checkbox)
        config_layout.addWidget(self.tts_checkbox)

        layout.addWidget(config_group)

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

        # 重载模式
        self.reload_checkbox = QCheckBox("启用自动重载 (开发模式)")
        server_layout.addWidget(self.reload_checkbox)

        layout.addWidget(server_group)

        # 控制按钮
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("启动服务")
        self.start_button.clicked.connect(self.start_server)
        self.start_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 10px; }")
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("停止服务")
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 10px; }")
        button_layout.addWidget(self.stop_button)

        layout.addLayout(button_layout)

        # 输出区域
        output_group = QGroupBox("服务器输出")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 9))
        output_layout.addWidget(self.output_text)

        layout.addWidget(output_group)

    def start_server(self):
        if self.server_thread and self.server_thread.isRunning():
            self.output_text.append("⚠️ 服务器已在运行")
            return

        host = self.host_input.text()
        port = self.port_input.text()
        enable_stt = self.stt_checkbox.isChecked()
        enable_tts = self.tts_checkbox.isChecked()
        reload_mode = self.reload_checkbox.isChecked()

        try:
            port_int = int(port)
        except ValueError:
            self.output_text.append("❌ 端口必须是数字")
            return

        self.output_text.clear()
        self.output_text.append("🚀 启动 VOXELINK 后端服务...")
        self.output_text.append(f"📍 主机: {host}")
        self.output_text.append(f"🔌 端口: {port_int}")
        self.output_text.append(f"🔄 重载: {'启用' if reload_mode else '禁用'}")

        services = ["后端"]
        if enable_stt:
            services.append("STT")
        if enable_tts:
            services.append("TTS")
        self.output_text.append(f"📦 启用的服务: {', '.join(services)}")

        self.server_thread = ServerThread(host, port_int, enable_stt, enable_tts, reload_mode)
        self.server_thread.output_signal.connect(self.append_output)
        self.server_thread.finished_signal.connect(self.on_server_finished)
        self.server_thread.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_server(self):
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread.wait(5000)
            self.on_server_finished()

    def append_output(self, text):
        self.output_text.append(text)

    def on_server_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)