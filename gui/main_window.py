#!/usr/bin/env python3
"""
VOXELINK GUI 主窗口模块

包含主要的GUI窗口类和相关功能。
"""

import sys
import os
import json
import base64
import tempfile
from pathlib import Path
import pyaudio
import wave
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QCheckBox, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QStackedWidget, QListWidget, QListWidgetItem, QComboBox, QProgressBar,
    QTextBrowser, QScrollArea, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import QThread, pyqtSignal, QProcess, QUrl, QTimer, QTime, QIODevice, QByteArray
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioSource, QAudioFormat, QAudioDevice, QMediaDevices
from PyQt6.QtWebSockets import QWebSocket
from PyQt6.QtNetwork import QAbstractSocket

from .threads import RecordingThread, ServerThread

# 导入配置
from backend.app.config.app_config import AppConfig


class VoxelinkGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化配置
        self.config = AppConfig()
        self.server_thread = None
        self.chat_websocket = None
        self.stt_websocket = None
        self.audio_player = None
        self.audio_output = None
        self.pyaudio_instance = None
        self.audio_stream = None
        self.recording_frames = []
        self.is_recording = False
        self.recorded_audio_file = None
        self.audio_queue = []
        self.is_playing = False
        # 实时STT相关变量
        self.stt_audio_context = None
        self.stt_media_stream = None
        self.stt_audio_processor = None
        self.stt_is_recording = False
        self.stt_is_connected = False
        self.stt_is_speaking = False
        self.stt_speech_frames = []
        self.stt_silence_frames = 0
        self.stt_pyaudio = None
        self.stt_stream = None
        self.stt_audio_timer = None
        # VAD配置 - 从配置文件读取
        self.stt_vad_config = self.config['gui']['vad']['stt']
        self.stt_audio_buffer = QByteArray()
        # 实时聊天相关变量
        self.realtime_chat_websocket = None
        self.realtime_chat_is_connected = False
        self.realtime_chat_is_recording = False
        self.realtime_chat_is_processing = False
        self.realtime_chat_speech_frames = []
        self.realtime_chat_silence_frames = 0
        self.realtime_chat_pyaudio = None
        self.realtime_chat_stream = None
        self.realtime_chat_audio_timer = None
        self.realtime_chat_audio_queue = []  # 实时聊天音频队列
        self.realtime_chat_is_playing = False  # 实时聊天音频播放状态
        # 实时聊天VAD配置 - 从配置文件读取
        self.realtime_chat_vad_config = self.config['gui']['vad']['realtime_chat']
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
        server_item = QListWidgetItem("🚀 启动管理")
        server_item.setFont(QFont("Arial", 11))
        self.nav_list.addItem(server_item)

        realtime_chat_item = QListWidgetItem("🔄 实时语音聊天")
        realtime_chat_item.setFont(QFont("Arial", 11))
        self.nav_list.addItem(realtime_chat_item)

        config_item = QListWidgetItem("⚙️ 配置文件管理")
        config_item.setFont(QFont("Arial", 11))
        self.nav_list.addItem(config_item)

        self.nav_list.currentRowChanged.connect(self.change_page)
        main_splitter.addWidget(self.nav_list)

        # 右侧内容区域
        self.stacked_widget = QStackedWidget()
        main_splitter.addWidget(self.stacked_widget)

        # 设置分割器比例
        main_splitter.setSizes([150, 850])

        # 创建启动管理页面
        self.create_server_page()

        # 创建实时语音聊天页面
        self.create_realtime_chat_page()

        # 创建配置文件管理页面
        self.create_config_page()

        # 设置默认页面
        self.nav_list.setCurrentRow(0)

        # 状态栏
        self.statusBar().showMessage("就绪")

    def change_page(self, index):
        self.stacked_widget.setCurrentIndex(index)

    def create_server_page(self):
        """创建启动管理页面"""
        server_widget = QWidget()
        layout = QVBoxLayout(server_widget)

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

        self.stacked_widget.addWidget(server_widget)

    def create_chat_page(self):
        """创建聊天页面"""
        chat_widget = QWidget()
        layout = QVBoxLayout(chat_widget)

        # 标题
        title_label = QLabel("💬 VOXELINK 语音聊天")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 连接状态
        status_group = QGroupBox("连接状态")
        status_layout = QVBoxLayout(status_group)

        self.chat_status_label = QLabel("未连接")
        self.chat_status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(self.chat_status_label)

        connect_layout = QHBoxLayout()
        self.connect_chat_btn = QPushButton("连接")
        self.connect_chat_btn.clicked.connect(self.connect_chat)
        connect_layout.addWidget(self.connect_chat_btn)

        self.disconnect_chat_btn = QPushButton("断开")
        self.disconnect_chat_btn.clicked.connect(self.disconnect_chat)
        self.disconnect_chat_btn.setEnabled(False)
        connect_layout.addWidget(self.disconnect_chat_btn)

        status_layout.addLayout(connect_layout)
        layout.addWidget(status_group)

        # 配置
        config_group = QGroupBox("配置")
        config_layout = QVBoxLayout(config_group)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("LLM模型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(self.config['gui']['models']['llm_models'])
        model_layout.addWidget(self.model_combo)
        config_layout.addLayout(model_layout)

        options_layout = QHBoxLayout()
        self.stream_checkbox = QCheckBox("流式输出")
        self.stream_checkbox.setChecked(True)
        self.tts_checkbox_chat = QCheckBox("启用TTS")
        self.tts_checkbox_chat.setChecked(True)
        options_layout.addWidget(self.stream_checkbox)
        options_layout.addWidget(self.tts_checkbox_chat)
        config_layout.addLayout(options_layout)

        self.update_config_btn = QPushButton("更新配置")
        self.update_config_btn.clicked.connect(self.update_chat_config)
        config_layout.addWidget(self.update_config_btn)

        layout.addWidget(config_group)

        # 录音控制
        record_group = QGroupBox("录音控制")
        record_layout = QVBoxLayout(record_group)

        record_btn_layout = QHBoxLayout()
        self.record_btn = QPushButton("开始录音")
        self.record_btn.clicked.connect(self.start_recording)
        record_btn_layout.addWidget(self.record_btn)

        self.stop_record_btn = QPushButton("停止录音")
        self.stop_record_btn.clicked.connect(self.stop_recording)
        self.stop_record_btn.setEnabled(False)
        record_btn_layout.addWidget(self.stop_record_btn)

        self.play_record_btn = QPushButton("播放录音")
        self.play_record_btn.clicked.connect(self.play_recording)
        self.play_record_btn.setEnabled(False)
        record_btn_layout.addWidget(self.play_record_btn)

        record_layout.addLayout(record_btn_layout)

        self.recording_status = QLabel("")
        record_layout.addWidget(self.recording_status)

        self.send_audio_btn = QPushButton("发送音频")
        self.send_audio_btn.clicked.connect(self.send_audio)
        self.send_audio_btn.setEnabled(False)
        record_layout.addWidget(self.send_audio_btn)

        layout.addWidget(record_group)

        # 处理结果
        results_group = QGroupBox("处理结果")
        results_layout = QVBoxLayout(results_group)

        self.transcription_label = QLabel("语音识别结果:")
        self.transcription_label.setVisible(False)
        results_layout.addWidget(self.transcription_label)

        self.transcription_text = QTextBrowser()
        self.transcription_text.setMaximumHeight(60)
        self.transcription_text.setVisible(False)
        results_layout.addWidget(self.transcription_text)

        self.response_label = QLabel("LLM回复:")
        self.response_label.setVisible(False)
        results_layout.addWidget(self.response_label)

        self.response_text = QTextBrowser()
        self.response_text.setMaximumHeight(100)
        self.response_text.setVisible(False)
        results_layout.addWidget(self.response_text)

        self.audio_label = QLabel("合成音频:")
        self.audio_label.setVisible(False)
        results_layout.addWidget(self.audio_label)

        audio_layout = QHBoxLayout()
        self.play_audio_btn = QPushButton("播放")
        self.play_audio_btn.clicked.connect(self.play_audio_response)
        self.play_audio_btn.setEnabled(False)
        audio_layout.addWidget(self.play_audio_btn)

        self.audio_progress = QProgressBar()
        self.audio_progress.setVisible(False)
        audio_layout.addWidget(self.audio_progress)

        results_layout.addLayout(audio_layout)

        layout.addWidget(results_group)

        self.stacked_widget.addWidget(chat_widget)

    def connect_chat(self):
        """连接到聊天WebSocket"""
        if self.chat_websocket:
            self.chat_websocket.close()

        self.chat_websocket = QWebSocket()
        self.chat_websocket.connected.connect(self.on_chat_connected)
        self.chat_websocket.disconnected.connect(self.on_chat_disconnected)
        self.chat_websocket.textMessageReceived.connect(self.on_chat_message)
        self.chat_websocket.binaryMessageReceived.connect(self.on_chat_binary_message)
        self.chat_websocket.errorOccurred.connect(self.on_chat_error)

        # 连接到pipeline WebSocket
        port = self.port_input.text()
        url = f"ws://localhost:{port}/ws/auto_pipeline"
        self.chat_websocket.open(QUrl(url))

        self.chat_status_label.setText("连接中...")
        self.chat_status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.connect_chat_btn.setEnabled(False)

    def disconnect_chat(self):
        """断开聊天连接"""
        if self.chat_websocket:
            self.chat_websocket.close()
        self.on_chat_disconnected()

    def on_chat_connected(self):
        """聊天连接成功"""
        self.chat_status_label.setText("已连接")
        self.chat_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.connect_chat_btn.setEnabled(False)
        self.disconnect_chat_btn.setEnabled(True)

    def on_chat_disconnected(self):
        """聊天连接断开"""
        self.chat_status_label.setText("未连接")
        self.chat_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.connect_chat_btn.setEnabled(True)
        self.disconnect_chat_btn.setEnabled(False)

    def on_chat_error(self, error):
        """聊天连接错误"""
        self.chat_status_label.setText(f"连接错误: {error}")
        self.chat_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.connect_chat_btn.setEnabled(True)
        self.disconnect_chat_btn.setEnabled(False)

    def on_chat_message(self, message):
        """接收聊天文本消息"""
        try:
            data = json.loads(message)
            self.handle_chat_message(data)
        except json.JSONDecodeError:
            print(f"收到无效JSON消息: {message}")

    def on_chat_binary_message(self, message):
        """接收聊天二进制消息（音频数据）"""
        # 处理音频数据
        self.audio_queue.append(message)
        self.play_next_audio()

    def handle_chat_message(self, data):
        """处理聊天消息"""
        if data.get("success"):
            if data.get("message"):
                # 连接或配置消息
                print(f"聊天消息: {data['message']}")
                return

            if data.get("type") == "stream_chunk":
                # 流式数据块
                chunk_data = data.get("data", {})

                if chunk_data.get("transcription"):
                    self.transcription_label.setVisible(True)
                    self.transcription_text.setVisible(True)
                    self.transcription_text.setText(chunk_data["transcription"])

                if chunk_data.get("text"):
                    self.response_label.setVisible(True)
                    self.response_text.setVisible(True)
                    current_text = self.response_text.toPlainText()
                    self.response_text.setText(current_text + chunk_data["text"])

                if chunk_data.get("audio"):
                    self.audio_label.setVisible(True)
                    self.play_audio_btn.setEnabled(True)
                    # 解码base64音频
                    audio_data = base64.b64decode(chunk_data["audio"])
                    self.audio_queue.append(audio_data)
                    self.play_next_audio()

            elif data.get("type") == "response":
                # 非流式响应
                response_data = data.get("data", {})

                if response_data.get("response_text"):
                    self.response_label.setVisible(True)
                    self.response_text.setVisible(True)
                    self.response_text.setText(response_data["response_text"])

                if response_data.get("audio"):
                    self.audio_label.setVisible(True)
                    self.play_audio_btn.setEnabled(True)
                    audio_data = base64.b64decode(response_data["audio"])
                    self.audio_queue.append(audio_data)
                    self.play_next_audio()

            self.chat_status_label.setText("处理完成")
            self.chat_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            # 错误消息
            error_msg = data.get("error", "未知错误")
            self.chat_status_label.setText(f"处理失败: {error_msg}")
            self.chat_status_label.setStyleSheet("color: red; font-weight: bold;")

    def update_chat_config(self):
        """更新聊天配置"""
        if not self.chat_websocket or self.chat_websocket.state() != QAbstractSocket.SocketState.ConnectedState:
            self.chat_status_label.setText("请先连接")
            self.chat_status_label.setStyleSheet("color: red; font-weight: bold;")
            return

        config = {
            "model": self.model_combo.currentText(),
            "stream": self.stream_checkbox.isChecked(),
            "tts": self.tts_checkbox_chat.isChecked()
        }

        message = json.dumps({
            "action": "config",
            "data": config
        })
        self.chat_websocket.sendTextMessage(message)

    def start_recording(self):
        """开始录音"""
        try:
            # 初始化PyAudio
            self.pyaudio_instance = pyaudio.PyAudio()

            # 设置音频参数
            self.chunk = 1024
            self.format = pyaudio.paInt16
            self.channels = 1
            self.rate = 16000

            # 打开音频流
            self.audio_stream = self.pyaudio_instance.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )

            self.recording_frames = []
            self.is_recording = True

            # 开始录音线程
            self.record_thread = RecordingThread(self.audio_stream, self.recording_frames)
            self.record_thread.finished.connect(self.on_recording_finished)
            self.record_thread.start()

            self.record_btn.setEnabled(False)
            self.stop_record_btn.setEnabled(True)
            self.recording_status.setText("正在录音...")
            self.recording_status.setStyleSheet("color: green;")

        except Exception as e:
            self.recording_status.setText(f"录音失败: {str(e)}")
            self.recording_status.setStyleSheet("color: red;")
            # 清理资源
            self.cleanup_recording_resources()

    def cleanup_recording_resources(self):
        """清理录音相关资源"""
        try:
            if hasattr(self, 'record_thread') and self.record_thread.isRunning():
                self.record_thread.stop_recording()
                self.record_thread.wait(1000)
        except:
            pass

        try:
            if self.audio_stream:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
        except:
            pass

        try:
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
        except:
            pass

        self.is_recording = False

    def stop_recording(self):
        """停止录音"""
        if self.is_recording:
            self.is_recording = False

            # 停止录音线程
            if hasattr(self, 'record_thread') and self.record_thread.isRunning():
                self.record_thread.stop_recording()
                self.record_thread.wait(1000)  # 等待最多1秒

            # 关闭音频流
            if self.audio_stream:
                try:
                    self.audio_stream.stop_stream()
                    self.audio_stream.close()
                except Exception as e:
                    print(f"关闭音频流异常: {e}")

            # 终止PyAudio实例
            if self.pyaudio_instance:
                try:
                    self.pyaudio_instance.terminate()
                except Exception as e:
                    print(f"终止PyAudio异常: {e}")

            # 保存录音到临时文件
            self.save_recording()

            self.record_btn.setEnabled(True)
            self.stop_record_btn.setEnabled(False)
            self.play_record_btn.setEnabled(True)
            self.send_audio_btn.setEnabled(True)
            self.recording_status.setText("录音完成")
            self.recording_status.setStyleSheet("color: black;")

    def save_recording(self):
        """保存录音到WAV文件"""
        try:
            # 创建临时文件
            temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
            os.close(temp_fd)  # 关闭文件描述符，让wave模块使用

            # 保存为WAV文件
            wf = wave.open(temp_path, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.pyaudio_instance.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(self.recording_frames))
            wf.close()

            self.recorded_audio_file = temp_path

        except Exception as e:
            self.recording_status.setText(f"保存录音失败: {str(e)}")
            self.recording_status.setStyleSheet("color: red;")

    def play_recording(self):
        """播放录音"""
        if self.recorded_audio_file and os.path.exists(self.recorded_audio_file):
            try:
                # 使用QMediaPlayer播放
                if not self.audio_player:
                    self.audio_player = QMediaPlayer()
                    self.audio_output = QAudioOutput()
                    self.audio_player.setAudioOutput(self.audio_output)

                self.audio_player.setSource(QUrl.fromLocalFile(self.recorded_audio_file))
                self.audio_player.play()

            except Exception as e:
                self.recording_status.setText(f"播放失败: {str(e)}")
        else:
            self.recording_status.setText("没有录音文件")

    def on_recording_finished(self):
        """录音线程完成"""
        pass

    def send_audio(self):
        """发送音频数据"""
        if not self.chat_websocket or self.chat_websocket.state() != QAbstractSocket.SocketState.ConnectedState:
            self.chat_status_label.setText("请先连接")
            self.chat_status_label.setStyleSheet("color: red; font-weight: bold;")
            return

        if not self.recorded_audio_file or not os.path.exists(self.recorded_audio_file):
            self.chat_status_label.setText("请先录音")
            self.chat_status_label.setStyleSheet("color: red; font-weight: bold;")
            return

        try:
            # 读取录音文件
            with open(self.recorded_audio_file, "rb") as f:
                audio_data = f.read()

            # 转换为base64
            base64_audio = base64.b64encode(audio_data).decode('utf-8')

            # 发送消息
            message = json.dumps({
                "action": "audio",
                "data": {
                    "audio_data": base64_audio,
                    "format": "wav"
                }
            })
            self.chat_websocket.sendTextMessage(message)

            # 清空之前的显示
            self.transcription_text.clear()
            self.response_text.clear()
            self.transcription_label.setVisible(False)
            self.transcription_text.setVisible(False)
            self.response_label.setVisible(False)
            self.response_text.setVisible(False)
            self.audio_label.setVisible(False)
            self.play_audio_btn.setEnabled(False)
            self.audio_queue.clear()

            self.chat_status_label.setText("处理中...")
            self.chat_status_label.setStyleSheet("color: orange; font-weight: bold;")

        except Exception as e:
            self.chat_status_label.setText(f"发送失败: {str(e)}")
            self.chat_status_label.setStyleSheet("color: red; font-weight: bold;")

    def play_next_audio(self):
        """播放下一个音频"""
        if self.audio_queue and not self.is_playing:
            try:
                audio_data = self.audio_queue.pop(0)
                # 保存为临时WAV文件
                temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
                os.close(temp_fd)

                # 写入WAV数据
                with open(temp_path, 'wb') as f:
                    f.write(audio_data)

                # 使用QMediaPlayer播放
                if not self.audio_player:
                    self.audio_player = QMediaPlayer()
                    self.audio_output = QAudioOutput()
                    self.audio_player.setAudioOutput(self.audio_output)

                self.audio_player.setSource(QUrl.fromLocalFile(temp_path))
                self.audio_player.play()
                self.is_playing = True

                # 播放完成后清理临时文件
                self.audio_player.mediaStatusChanged.connect(
                    lambda status: self.on_audio_finished(temp_path) if status == QMediaPlayer.MediaStatus.EndOfMedia else None
                )

            except Exception as e:
                print(f"播放音频失败: {e}")
                self.is_playing = False

    def on_audio_finished(self, temp_path):
        """音频播放完成"""
        self.is_playing = False
        try:
            os.remove(temp_path)
        except:
            pass
        # 播放下一个音频
        self.play_next_audio()

    def play_audio_response(self):
        """播放音频回复"""
        if self.audio_queue:
            self.play_next_audio()
        else:
            print("没有音频数据可播放")

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
        self.statusBar().showMessage("服务器启动中...")

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
        self.statusBar().showMessage("服务器已停止")

    def create_realtime_chat_page(self):
        """创建实时语音聊天页面"""
        chat_widget = QWidget()
        layout = QVBoxLayout(chat_widget)

        # 标题
        title_label = QLabel("🔄 VOXELINK 实时语音聊天")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 连接状态
        status_group = QGroupBox("连接状态")
        status_layout = QVBoxLayout(status_group)

        self.realtime_chat_status_label = QLabel("未连接")
        self.realtime_chat_status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(self.realtime_chat_status_label)

        connect_layout = QHBoxLayout()
        self.realtime_chat_connect_btn = QPushButton("连接")
        self.realtime_chat_connect_btn.clicked.connect(self.realtime_chat_connect)
        connect_layout.addWidget(self.realtime_chat_connect_btn)

        self.realtime_chat_disconnect_btn = QPushButton("断开")
        self.realtime_chat_disconnect_btn.clicked.connect(self.realtime_chat_disconnect)
        self.realtime_chat_disconnect_btn.setEnabled(False)
        connect_layout.addWidget(self.realtime_chat_disconnect_btn)

        status_layout.addLayout(connect_layout)
        layout.addWidget(status_group)

        # 配置
        config_group = QGroupBox("配置")
        config_layout = QVBoxLayout(config_group)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("LLM模型:"))
        self.realtime_chat_model_combo = QComboBox()
        self.realtime_chat_model_combo.addItems(self.config['gui']['models']['llm_models'])
        model_layout.addWidget(self.realtime_chat_model_combo)
        config_layout.addLayout(model_layout)

        options_layout = QHBoxLayout()
        self.realtime_chat_stream_checkbox = QCheckBox("流式输出")
        self.realtime_chat_stream_checkbox.setChecked(True)
        self.realtime_chat_tts_checkbox = QCheckBox("启用TTS")
        self.realtime_chat_tts_checkbox.setChecked(True)
        options_layout.addWidget(self.realtime_chat_stream_checkbox)
        options_layout.addWidget(self.realtime_chat_tts_checkbox)
        config_layout.addLayout(options_layout)

        self.realtime_chat_update_config_btn = QPushButton("更新配置")
        self.realtime_chat_update_config_btn.clicked.connect(self.realtime_chat_update_config)
        config_layout.addWidget(self.realtime_chat_update_config_btn)

        layout.addWidget(config_group)

        # 实时控制
        control_group = QGroupBox("实时控制")
        control_layout = QVBoxLayout(control_group)

        # 录音控制
        record_layout = QHBoxLayout()
        self.realtime_chat_record_btn = QPushButton("开始实时录音")
        self.realtime_chat_record_btn.clicked.connect(self.realtime_chat_start_recording)
        record_layout.addWidget(self.realtime_chat_record_btn)

        self.realtime_chat_stop_record_btn = QPushButton("停止录音")
        self.realtime_chat_stop_record_btn.clicked.connect(self.realtime_chat_stop_recording)
        self.realtime_chat_stop_record_btn.setEnabled(False)
        self.realtime_chat_stop_record_btn.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; }")
        record_layout.addWidget(self.realtime_chat_stop_record_btn)

        control_layout.addLayout(record_layout)

        # 状态指示器
        status_indicator_layout = QHBoxLayout()
        self.realtime_chat_voice_indicator = QLabel("●")
        self.realtime_chat_voice_indicator.setStyleSheet("color: #bdc3c7; font-size: 20px;")
        status_indicator_layout.addWidget(self.realtime_chat_voice_indicator)

        self.realtime_chat_voice_status = QLabel("未检测到语音")
        status_indicator_layout.addWidget(self.realtime_chat_voice_status)

        self.realtime_chat_processing_status = QLabel("等待语音输入")
        self.realtime_chat_processing_status.setStyleSheet("color: blue; font-weight: bold;")
        status_indicator_layout.addWidget(self.realtime_chat_processing_status)

        control_layout.addLayout(status_indicator_layout)

        layout.addWidget(control_group)

        # VAD调试面板
        vad_group = QGroupBox("VAD 实时调试信息")
        vad_layout = QVBoxLayout(vad_group)

        # VAD仪表
        vad_meter_layout = QHBoxLayout()
        self.realtime_chat_vad_meter = QProgressBar()
        self.realtime_chat_vad_meter.setMaximum(100)
        self.realtime_chat_vad_meter.setValue(0)
        vad_meter_layout.addWidget(QLabel("VAD水平:"))
        vad_meter_layout.addWidget(self.realtime_chat_vad_meter)
        vad_layout.addLayout(vad_meter_layout)

        # VAD统计信息
        vad_stats_layout = QHBoxLayout()
        self.realtime_chat_vad_rms = QLabel("RMS: 0.000")
        self.realtime_chat_vad_threshold = QLabel("阈值: 0.150")
        vad_stats_layout.addWidget(self.realtime_chat_vad_rms)
        vad_stats_layout.addWidget(self.realtime_chat_vad_threshold)
        vad_layout.addLayout(vad_stats_layout)

        layout.addWidget(vad_group)

        # 聊天记录
        chat_group = QGroupBox("聊天记录")
        chat_layout = QVBoxLayout(chat_group)

        self.realtime_chat_text = QTextBrowser()
        self.realtime_chat_text.setMinimumHeight(200)
        chat_layout.addWidget(self.realtime_chat_text)

        clear_chat_layout = QHBoxLayout()
        self.realtime_chat_clear_btn = QPushButton("清空记录")
        self.realtime_chat_clear_btn.clicked.connect(self.realtime_chat_clear)
        clear_chat_layout.addWidget(self.realtime_chat_clear_btn)

        self.realtime_chat_save_btn = QPushButton("保存记录")
        self.realtime_chat_save_btn.clicked.connect(self.realtime_chat_save)
        clear_chat_layout.addWidget(self.realtime_chat_save_btn)

        chat_layout.addLayout(clear_chat_layout)
        layout.addWidget(chat_group)

        self.stacked_widget.addWidget(chat_widget)

    def create_config_page(self):
        """创建配置文件管理页面"""
        config_widget = QWidget()
        layout = QVBoxLayout(config_widget)

        # 标题
        title_label = QLabel("⚙️ VOXELINK 配置文件管理")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 滚动区域
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # 加载配置文件
        self.config_data = self.load_config()
        self.config_widgets = {}

        # 为每个顶级配置创建组
        for section_name, section_data in self.config_data.items():
            group = QGroupBox(section_name.upper())
            group_layout = QVBoxLayout(group)
            self.create_config_section(group_layout, section_data, section_name)
            scroll_layout.addWidget(group)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # 保存按钮
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_config)
        layout.addWidget(save_btn)

        self.stacked_widget.addWidget(config_widget)

    def load_config(self):
        """加载配置文件"""
        config_path = Path(__file__).parent.parent / "backend" / "config.json"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {}

    def create_config_section(self, layout, data, prefix=""):
        """递归创建配置控件"""
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    # 嵌套对象，创建子组
                    sub_group = QGroupBox(key)
                    sub_layout = QVBoxLayout(sub_group)
                    self.create_config_section(sub_layout, value, full_key)
                    layout.addWidget(sub_group)
                else:
                    # 叶子节点，创建控件
                    self.create_config_control(layout, full_key, key, value)
        elif isinstance(data, list):
            # 列表，暂时不支持编辑
            label = QLabel(f"{prefix}: {str(data)} (列表，暂不支持编辑)")
            layout.addWidget(label)
        else:
            # 其他类型
            self.create_config_control(layout, prefix, prefix.split('.')[-1], data)

    def create_config_control(self, layout, full_key, label_text, value):
        """创建单个配置控件"""
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel(f"{label_text}:"))

        if isinstance(value, bool):
            widget = QCheckBox()
            widget.setChecked(value)
        elif isinstance(value, int):
            widget = QSpinBox()
            widget.setRange(-999999, 999999)
            widget.setValue(value)
        elif isinstance(value, float):
            widget = QDoubleSpinBox()
            widget.setRange(-999999.0, 999999.0)
            widget.setValue(value)
        elif isinstance(value, str):
            widget = QLineEdit(str(value))
        else:
            widget = QLineEdit(str(value))

        h_layout.addWidget(widget)
        layout.addLayout(h_layout)
        self.config_widgets[full_key] = widget

    def save_config(self):
        """保存配置"""
        # 从控件收集数据
        new_config = self.collect_config_data(self.config_data, "")

        # 保存到文件
        config_path = Path(__file__).parent.parent / "backend" / "config.json"
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=2, ensure_ascii=False)
            self.statusBar().showMessage("配置已保存")
        except Exception as e:
            self.statusBar().showMessage(f"保存配置失败: {e}")

    def collect_config_data(self, original, prefix):
        """从控件收集配置数据"""
        if isinstance(original, dict):
            result = {}
            for key, value in original.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    result[key] = self.collect_config_data(value, full_key)
                else:
                    widget = self.config_widgets.get(full_key)
                    if widget:
                        if isinstance(widget, QCheckBox):
                            result[key] = widget.isChecked()
                        elif isinstance(widget, QSpinBox):
                            result[key] = widget.value()
                        elif isinstance(widget, QDoubleSpinBox):
                            result[key] = widget.value()
                        elif isinstance(widget, QLineEdit):
                            text = widget.text()
                            # 尝试转换类型
                            if isinstance(value, int):
                                try:
                                    result[key] = int(text)
                                except:
                                    result[key] = text
                            elif isinstance(value, float):
                                try:
                                    result[key] = float(text)
                                except:
                                    result[key] = text
                            else:
                                result[key] = text
                        else:
                            result[key] = value
                    else:
                        result[key] = value
            return result
        else:
            return original

    def create_realtime_stt_page(self):
        """创建实时语音识别页面"""
        stt_widget = QWidget()
        layout = QVBoxLayout(stt_widget)

        # 标题
        title_label = QLabel("🎤 VOXELINK 实时语音识别")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 连接状态
        status_group = QGroupBox("连接状态")
        status_layout = QVBoxLayout(status_group)

        self.stt_status_label = QLabel("未连接")
        self.stt_status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(self.stt_status_label)

        connect_layout = QHBoxLayout()
        self.stt_connect_btn = QPushButton("连接服务器")
        self.stt_connect_btn.clicked.connect(self.stt_connect)
        connect_layout.addWidget(self.stt_connect_btn)

        self.stt_disconnect_btn = QPushButton("断开连接")
        self.stt_disconnect_btn.clicked.connect(self.stt_disconnect)
        self.stt_disconnect_btn.setEnabled(False)
        connect_layout.addWidget(self.stt_disconnect_btn)

        status_layout.addLayout(connect_layout)
        layout.addWidget(status_group)

        # 设置
        settings_group = QGroupBox("设置")
        settings_layout = QVBoxLayout(settings_group)

        # 服务器配置
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel("服务器地址:"))
        self.stt_server_url = QLineEdit(self.config['gui']['server']['stt_ws_url'])
        server_layout.addWidget(self.stt_server_url)
        settings_layout.addLayout(server_layout)

        # 用户配置
        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("用户Token:"))
        self.stt_user_token = QLineEdit()
        user_layout.addWidget(self.stt_user_token)
        settings_layout.addLayout(user_layout)

        llm_layout = QHBoxLayout()
        llm_layout.addWidget(QLabel("LLM API地址:"))
        self.stt_llm_api_url = QLineEdit()
        llm_layout.addWidget(self.stt_llm_api_url)
        settings_layout.addLayout(llm_layout)

        # 选项
        options_layout = QHBoxLayout()
        self.stt_check_voiceprint = QCheckBox("启用声纹识别")
        self.stt_only_register_user = QCheckBox("仅识别注册用户")
        self.stt_identify_unregistered = QCheckBox("识别未注册用户")
        options_layout.addWidget(self.stt_check_voiceprint)
        options_layout.addWidget(self.stt_only_register_user)
        options_layout.addWidget(self.stt_identify_unregistered)
        settings_layout.addLayout(options_layout)

        layout.addWidget(settings_group)

        # 控制按钮
        controls_layout = QHBoxLayout()
        self.stt_start_btn = QPushButton("开始录音")
        self.stt_start_btn.clicked.connect(self.stt_start_recording)
        self.stt_start_btn.setEnabled(False)
        controls_layout.addWidget(self.stt_start_btn)

        self.stt_stop_btn = QPushButton("停止录音")
        self.stt_stop_btn.clicked.connect(self.stt_stop_recording)
        self.stt_stop_btn.setEnabled(False)
        self.stt_stop_btn.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; }")
        controls_layout.addWidget(self.stt_stop_btn)

        self.stt_clear_btn = QPushButton("清空记录")
        self.stt_clear_btn.clicked.connect(self.stt_clear_transcript)
        controls_layout.addWidget(self.stt_clear_btn)

        layout.addLayout(controls_layout)

        # 语音活动指示器
        voice_group = QGroupBox("语音活动")
        voice_layout = QHBoxLayout(voice_group)

        self.stt_voice_indicator = QLabel("●")
        self.stt_voice_indicator.setStyleSheet("color: #bdc3c7; font-size: 20px;")
        voice_layout.addWidget(self.stt_voice_indicator)

        self.stt_voice_status = QLabel("未检测到语音")
        voice_layout.addWidget(self.stt_voice_status)

        layout.addWidget(voice_group)

        # 录音状态
        self.stt_recording_status = QLabel("未开始录音")
        self.stt_recording_status.setStyleSheet("background-color: #e8f4fd; padding: 8px; border-radius: 4px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.stt_recording_status)

        # VAD调试面板
        vad_group = QGroupBox("VAD 实时调试信息")
        vad_layout = QVBoxLayout(vad_group)

        # VAD仪表
        vad_meter_layout = QHBoxLayout()
        self.stt_vad_meter = QProgressBar()
        self.stt_vad_meter.setMaximum(100)
        self.stt_vad_meter.setValue(0)
        vad_meter_layout.addWidget(QLabel("VAD水平:"))
        vad_meter_layout.addWidget(self.stt_vad_meter)
        vad_layout.addLayout(vad_meter_layout)

        # VAD统计信息
        vad_stats_layout = QHBoxLayout()
        self.stt_vad_rms = QLabel("RMS: 0.000")
        self.stt_vad_threshold = QLabel("阈值: 0.150")
        self.stt_vad_confidence = QLabel("置信度: 0.000")
        self.stt_vad_status_label = QLabel("状态: 未检测")
        vad_stats_layout.addWidget(self.stt_vad_rms)
        vad_stats_layout.addWidget(self.stt_vad_threshold)
        vad_stats_layout.addWidget(self.stt_vad_confidence)
        vad_stats_layout.addWidget(self.stt_vad_status_label)
        vad_layout.addLayout(vad_stats_layout)

        self.stt_audio_duration = QLabel("音频时长: 0.00s")
        vad_layout.addWidget(self.stt_audio_duration)

        layout.addWidget(vad_group)

        # 转录结果
        transcript_group = QGroupBox("转录结果")
        transcript_layout = QVBoxLayout(transcript_group)

        self.stt_transcript = QTextBrowser()
        self.stt_transcript.setMinimumHeight(200)
        transcript_layout.addWidget(self.stt_transcript)

        layout.addWidget(transcript_group)

        self.stacked_widget.addWidget(stt_widget)

    def stt_connect(self):
        """连接到实时STT WebSocket"""
        if self.stt_websocket:
            self.stt_websocket.close()

        server_url = self.stt_server_url.text()
        if not server_url:
            self.stt_add_message("请输入服务器地址", True, True)
            return

        try:
            self.stt_add_message(f"正在连接到 {server_url}...", True)
            self.stt_websocket = QWebSocket()
            self.stt_websocket.connected.connect(self.stt_on_connected)
            self.stt_websocket.disconnected.connect(self.stt_on_disconnected)
            self.stt_websocket.textMessageReceived.connect(self.stt_on_message)
            self.stt_websocket.errorOccurred.connect(self.stt_on_error)

            self.stt_websocket.open(QUrl(server_url))

            self.stt_status_label.setText("连接中...")
            self.stt_status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.stt_connect_btn.setEnabled(False)

        except Exception as e:
            self.stt_add_message(f"连接错误: {str(e)}", False, True)
            self.stt_update_status(False)

    def stt_disconnect(self):
        """断开实时STT连接"""
        if self.stt_websocket:
            self.stt_websocket.close()
        self.stt_stop_recording()
        self.stt_on_disconnected()

    def stt_on_connected(self):
        """实时STT连接成功"""
        self.stt_is_connected = True
        self.stt_status_label.setText("已连接")
        self.stt_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.stt_connect_btn.setEnabled(False)
        self.stt_disconnect_btn.setEnabled(True)
        self.stt_start_btn.setEnabled(True)
        self.stt_add_message("已连接到实时语音识别服务", True)
        
        # 发送配置信息
        self.stt_send_config()

    def stt_send_config(self):
        """发送配置信息到服务器"""
        if not self.stt_websocket or self.stt_websocket.state() != QAbstractSocket.SocketState.ConnectedState:
            return

        config = {
            "user_token": self.stt_user_token.text().strip(),
            "llm_api_url": self.stt_llm_api_url.text().strip(),
            "check_voiceprint": self.stt_check_voiceprint.isChecked(),
            "only_register_user": self.stt_only_register_user.isChecked(),
            "identify_unregistered": self.stt_identify_unregistered.isChecked()
        }

        message = json.dumps({
            "action": "config",
            "data": config
        })

        try:
            self.stt_websocket.sendTextMessage(message)
            self.stt_add_message("配置已发送", True)
        except Exception as e:
            self.stt_add_message(f"发送配置失败: {str(e)}", False, True)

    def stt_on_disconnected(self):
        """实时STT连接断开"""
        self.stt_is_connected = False
        self.stt_status_label.setText("未连接")
        self.stt_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.stt_connect_btn.setEnabled(True)
        self.stt_disconnect_btn.setEnabled(False)
        self.stt_start_btn.setEnabled(False)
        self.stt_stop_btn.setEnabled(False)

    def stt_on_error(self, error):
        """实时STT连接错误"""
        self.stt_status_label.setText(f"连接错误: {error}")
        self.stt_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.stt_connect_btn.setEnabled(True)
        self.stt_disconnect_btn.setEnabled(False)
        self.stt_start_btn.setEnabled(False)

    def stt_on_message(self, message):
        """处理实时STT消息"""
        try:
            data = json.loads(message)
            self.stt_handle_message(data)
        except json.JSONDecodeError:
            self.stt_add_message(f"收到无效JSON消息: {message}", False, True)

    def stt_handle_message(self, data):
        """处理实时STT消息"""
        if data.get("success"):
            if data.get("text"):
                # 转录结果
                self.stt_add_message(data["text"], False)
            elif data.get("message"):
                # 系统消息
                self.stt_add_message(data["message"], True)
        else:
            # 错误消息
            error_msg = data.get("error", "未知错误")
            self.stt_add_message(f"错误: {error_msg}", False, True)

    def stt_start_recording(self):
        """开始实时录音"""
        if not self.stt_is_connected:
            self.stt_add_message("请先连接到服务器", False, True)
            return

        try:
            self.stt_add_message("开始录音...", True)
            self.stt_is_recording = True
            self.stt_start_btn.setEnabled(False)
            self.stt_stop_btn.setEnabled(True)
            self.stt_recording_status.setText("正在录音")
            self.stt_recording_status.setStyleSheet("background-color: #d4edda; color: #155724;")

            # 使用pyaudio进行录音
            self.stt_pyaudio = pyaudio.PyAudio()
            self.stt_stream = self.stt_pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.stt_vad_config['channels'],
                rate=self.stt_vad_config['sample_rate'],
                input=True,
                frames_per_buffer=self.stt_vad_config['chunk_size']
            )

            # 使用定时器定期读取音频数据
            self.stt_audio_timer = QTimer()
            self.stt_audio_timer.timeout.connect(self.stt_process_audio_data)
            self.stt_audio_timer.start(100)  # 每100ms读取一次
            self.stt_add_message("音频录制已启动", True)

        except Exception as e:
            self.stt_add_message(f"录音失败: {str(e)}", False, True)
            self.stt_is_recording = False
            self.stt_start_btn.setEnabled(True)
            self.stt_stop_btn.setEnabled(False)

    def stt_stop_recording(self):
        """停止实时录音"""
        if self.stt_is_recording:
            self.stt_is_recording = False
            if self.stt_audio_timer:
                self.stt_audio_timer.stop()
                self.stt_audio_timer = None
            if hasattr(self, 'stt_stream') and self.stt_stream:
                self.stt_stream.stop_stream()
                self.stt_stream.close()
            if hasattr(self, 'stt_pyaudio') and self.stt_pyaudio:
                self.stt_pyaudio.terminate()
            self.stt_start_btn.setEnabled(True)
            self.stt_stop_btn.setEnabled(False)
            self.stt_recording_status.setText("录音已停止")
            self.stt_recording_status.setStyleSheet("background-color: #f8d7da; color: #721c24;")
            self.stt_add_message("录音已停止", True)

    def stt_process_audio_data(self):
        """处理音频数据"""
        if not self.stt_is_recording or not hasattr(self, 'stt_stream'):
            return

        try:
            # 从pyaudio流读取数据
            audio_bytes = self.stt_stream.read(self.stt_vad_config['chunk_size'], exception_on_overflow=False)
            
            if len(audio_bytes) > 0:
                # 计算RMS值用于VAD
                rms = self.stt_calculate_rms(audio_bytes)
                self.stt_update_vad_display(rms)
                
                # 简单的VAD逻辑
                is_speech = rms > self.stt_vad_config['vad_threshold']
                self.stt_update_voice_activity(is_speech)
                
                # 如果检测到语音，开始收集音频数据
                if is_speech:
                    self.stt_speech_frames.append(audio_bytes)
                    self.stt_silence_frames = 0
                else:
                    if self.stt_speech_frames:
                        self.stt_silence_frames += 1
                        # 如果静音持续时间超过阈值，发送已收集的音频
                        if self.stt_silence_frames >= self.stt_vad_config['max_silence_frames']:
                            self.stt_send_audio_chunk()
                
        except Exception as e:
            self.stt_add_message(f"音频处理错误: {str(e)}", False, True)

    def stt_calculate_rms(self, audio_data):
        """计算音频数据的RMS值"""
        if len(audio_data) == 0:
            return 0.0
        
        # 将字节数据转换为16位整数
        int16_array = []
        for i in range(0, len(audio_data), 2):
            if i + 1 < len(audio_data):
                # 小端字节序
                sample = int.from_bytes(audio_data[i:i+2], byteorder='little', signed=True)
                int16_array.append(sample)
        
        if not int16_array:
            return 0.0
        
        # 计算RMS
        sum_squares = sum(x * x for x in int16_array)
        rms = (sum_squares / len(int16_array)) ** 0.5
        
        # 归一化到0-1范围 (16位音频的最大值是32767)
        return rms / 32767.0

    def stt_update_vad_display(self, rms):
        """更新VAD显示"""
        # 更新RMS显示
        self.stt_vad_rms.setText(f"RMS: {rms:.3f}")
        
        # 更新VAD仪表
        vad_level = min(int(rms * 100), 100)
        self.stt_vad_meter.setValue(vad_level)
        
        # 更新阈值显示
        threshold = self.stt_vad_config['vad_threshold']
        self.stt_vad_threshold.setText(f"阈值: {threshold:.3f}")
        
        # 更新置信度 (这里简化为RMS值)
        self.stt_vad_confidence.setText(f"置信度: {rms:.3f}")

    def stt_update_voice_activity(self, is_active):
        """更新语音活动指示器"""
        if is_active != self.stt_is_speaking:
            self.stt_is_speaking = is_active
            if is_active:
                self.stt_voice_indicator.setStyleSheet("color: #2ecc71; font-size: 20px;")
                self.stt_voice_status.setText("检测到语音 (正在识别)")
                self.stt_vad_status_label.setText("状态: 检测到语音")
            else:
                self.stt_voice_indicator.setStyleSheet("color: #bdc3c7; font-size: 20px;")
                self.stt_voice_status.setText("未检测到语音")
                self.stt_vad_status_label.setText("状态: 未检测")

    def stt_send_audio_chunk(self):
        """发送音频块到服务器"""
        if not self.stt_speech_frames or not self.stt_websocket:
            return
        
        try:
            # 合并所有语音帧
            combined_audio = b''.join(self.stt_speech_frames)
            
            # 转换为base64
            base64_audio = base64.b64encode(combined_audio).decode('utf-8')
            
            # 发送到WebSocket
            message = json.dumps({
                "action": "audio",
                "data": {
                    "audio_data": base64_audio,
                    "format": "pcm",
                    "sample_rate": self.stt_vad_config['sample_rate'],
                    "channels": self.stt_vad_config['channels']
                }
            })
            
            self.stt_websocket.sendTextMessage(message)
            
            # 清空已发送的帧
            self.stt_speech_frames.clear()
            self.stt_silence_frames = 0
            
        except Exception as e:
            self.stt_add_message(f"发送音频失败: {str(e)}", False, True)

    def stt_clear_transcript(self):
        """清空转录结果"""
        self.stt_transcript.clear()
        self.stt_add_message("记录已清空", True)

    def stt_add_message(self, text, is_system=False, is_error=False):
        """添加消息到转录结果"""
        timestamp = QTime.currentTime().toString("hh:mm:ss")
        message_type = ""
        if is_error:
            message_type = " [错误]"
        elif is_system:
            message_type = " [系统]"

        self.stt_transcript.append(f"[{timestamp}]{message_type} {text}")
        # 滚动到底部
        scrollbar = self.stt_transcript.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.stop_server()
        self.disconnect_chat()
        self.stt_disconnect()
        self.realtime_chat_disconnect()

        # 清理录音资源
        self.cleanup_recording_resources()

        if self.recorded_audio_file and os.path.exists(self.recorded_audio_file):
            try:
                os.remove(self.recorded_audio_file)
            except:
                pass

        event.accept()
        self.cleanup_recording_resources()

        if self.recorded_audio_file and os.path.exists(self.recorded_audio_file):
            try:
                os.remove(self.recorded_audio_file)
            except:
                pass

        event.accept()

    # ==================== 实时聊天相关方法 ====================

    def realtime_chat_connect(self):
        """连接到实时聊天WebSocket"""
        # 如果已经连接，先断开
        if self.realtime_chat_is_connected:
            self.realtime_chat_disconnect()

        # 创建新的WebSocket
        self.realtime_chat_websocket = QWebSocket()
        self.realtime_chat_websocket.connected.connect(self.on_realtime_chat_connected)
        self.realtime_chat_websocket.disconnected.connect(self.on_realtime_chat_disconnected)
        self.realtime_chat_websocket.textMessageReceived.connect(self.on_realtime_chat_message)
        self.realtime_chat_websocket.binaryMessageReceived.connect(self.on_realtime_chat_binary_message)

        # 连接到自动pipeline WebSocket
        url = self.config['gui']['server']['auto_pipeline_ws_url']
        self.realtime_chat_websocket.open(QUrl(url))

        self.realtime_chat_status_label.setText("连接中...")
        self.realtime_chat_status_label.setStyleSheet("color: orange; font-weight: bold;")

    def realtime_chat_disconnect(self):
        """断开实时聊天WebSocket连接"""
        if self.realtime_chat_websocket and self.realtime_chat_is_connected:
            self.realtime_chat_websocket.close()
            self.realtime_chat_websocket = None
            self.realtime_chat_is_connected = False

        self.realtime_chat_stop_recording()
        self.realtime_chat_status_label.setText("已断开")
        self.realtime_chat_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.realtime_chat_connect_btn.setEnabled(True)
        self.realtime_chat_disconnect_btn.setEnabled(False)
        self.realtime_chat_record_btn.setEnabled(False)

    def on_realtime_chat_connected(self):
        """实时聊天WebSocket连接成功"""
        self.realtime_chat_is_connected = True
        self.realtime_chat_status_label.setText("已连接")
        self.realtime_chat_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.realtime_chat_connect_btn.setEnabled(False)
        self.realtime_chat_disconnect_btn.setEnabled(True)
        self.realtime_chat_record_btn.setEnabled(True)
        self.realtime_chat_add_message("实时聊天WebSocket连接成功", "system")
        
        # 连接成功后自动发送配置
        self.realtime_chat_update_config()

    def on_realtime_chat_disconnected(self):
        """实时聊天WebSocket断开连接"""
        self.realtime_chat_is_connected = False
        # 只更新UI状态，不要调用disconnect方法（避免递归）
        self.realtime_chat_stop_recording()
        self.realtime_chat_status_label.setText("已断开")
        self.realtime_chat_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.realtime_chat_connect_btn.setEnabled(True)
        self.realtime_chat_disconnect_btn.setEnabled(False)
        self.realtime_chat_record_btn.setEnabled(False)
        self.realtime_chat_add_message("连接已断开", "system")

    def on_realtime_chat_message(self, message):
        """接收实时聊天文本消息"""
        try:
            data = json.loads(message)
            self.handle_realtime_chat_message(data)
        except json.JSONDecodeError:
            print(f"收到无效JSON消息: {message}")

    def on_realtime_chat_binary_message(self, message):
        """接收实时聊天二进制消息（音频数据）"""
        # 处理TTS音频数据
        self.realtime_chat_audio_queue.append(message)
        self.realtime_chat_play_next_audio()

    def handle_realtime_chat_message(self, data):
        """处理实时聊天消息"""
        if data.get("success"):
            if data.get("message"):
                # 连接或配置消息
                self.realtime_chat_add_message(data['message'], "system")
                return

            msg_type = data.get("type", "")

            if msg_type == "stt_result":
                # STT结果
                stt_data = data.get("data", {})
                if stt_data.get("transcription"):
                    self.realtime_chat_add_message(f"语音识别: {stt_data['transcription']}", "stt")
                    self.realtime_chat_add_message("正在生成回复...", "system")

            elif msg_type == "stream_chunk":
                # 流式数据块
                chunk_data = data.get("data", {})

                if chunk_data.get("transcription"):
                    self.realtime_chat_add_message(f"语音识别: {chunk_data['transcription']}", "stt")

                if chunk_data.get("text"):
                    self.realtime_chat_add_message(chunk_data["text"], "llm", append=True)

                if chunk_data.get("audio"):
                    # 解码base64音频并添加到队列
                    audio_data = base64.b64decode(chunk_data["audio"])
                    self.realtime_chat_audio_queue.append(audio_data)
                    self.realtime_chat_play_next_audio()

            elif msg_type == "response":
                # 非流式响应
                response_data = data.get("data", {})

                if response_data.get("response_text"):
                    self.realtime_chat_add_message(response_data["response_text"], "llm")

                if response_data.get("audio"):
                    audio_data = base64.b64decode(response_data["audio"])
                    self.realtime_chat_audio_queue.append(audio_data)
                    self.realtime_chat_play_next_audio()

            elif msg_type == "complete":
                # 处理完成
                self.realtime_chat_add_message("处理完成", "system")

            # 处理完成后允许再次录音
            if msg_type in ["stt_result", "response", "complete"]:
                self.realtime_chat_is_processing = False
                self.realtime_chat_processing_status.setText("等待语音输入")
                self.realtime_chat_processing_status.setStyleSheet("color: blue; font-weight: bold;")
        else:
            # 错误消息
            error_msg = data.get("error", "未知错误")
            self.realtime_chat_add_message(f"处理失败: {error_msg}", "error")
            self.realtime_chat_is_processing = False
            self.realtime_chat_processing_status.setText("等待语音输入")
            self.realtime_chat_processing_status.setStyleSheet("color: blue; font-weight: bold;")

    def realtime_chat_update_config(self):
        """更新实时聊天配置"""
        if not self.realtime_chat_websocket or self.realtime_chat_websocket.state() != QAbstractSocket.SocketState.ConnectedState:
            self.realtime_chat_status_label.setText("请先连接")
            self.realtime_chat_status_label.setStyleSheet("color: red; font-weight: bold;")
            return

        config = {
            "model": self.realtime_chat_model_combo.currentText(),
            "stream": self.realtime_chat_stream_checkbox.isChecked(),
            "tts": self.realtime_chat_tts_checkbox.isChecked()
        }

        message = json.dumps({
            "action": "config",
            "data": config
        })
        self.realtime_chat_websocket.sendTextMessage(message)
        self.realtime_chat_add_message("配置已更新", "system")

    def realtime_chat_start_recording(self):
        """开始实时录音"""
        if not self.realtime_chat_websocket or self.realtime_chat_websocket.state() != QAbstractSocket.SocketState.ConnectedState:
            self.realtime_chat_add_message("请先连接到服务器", "error")
            return

        try:
            self.realtime_chat_add_message("开始实时录音...", "system")
            self.realtime_chat_is_recording = True
            self.realtime_chat_is_processing = False
            self.realtime_chat_record_btn.setEnabled(False)
            self.realtime_chat_stop_record_btn.setEnabled(True)
            self.realtime_chat_processing_status.setText("正在录音")
            self.realtime_chat_processing_status.setStyleSheet("color: green; font-weight: bold;")

            # 初始化PyAudio
            self.realtime_chat_pyaudio = pyaudio.PyAudio()
            self.realtime_chat_stream = self.realtime_chat_pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.realtime_chat_vad_config['channels'],
                rate=self.realtime_chat_vad_config['sample_rate'],
                input=True,
                frames_per_buffer=self.realtime_chat_vad_config['chunk_size']
            )

            # 使用定时器定期读取音频数据
            self.realtime_chat_audio_timer = QTimer()
            self.realtime_chat_audio_timer.timeout.connect(self.realtime_chat_process_audio_data)
            self.realtime_chat_audio_timer.start(100)  # 每100ms读取一次
            self.realtime_chat_add_message("音频录制已启动", "system")

        except Exception as e:
            self.realtime_chat_add_message(f"录音失败: {str(e)}", "error")
            self.realtime_chat_is_recording = False
            self.realtime_chat_record_btn.setEnabled(True)
            self.realtime_chat_stop_record_btn.setEnabled(False)

    def realtime_chat_stop_recording(self):
        """停止实时录音"""
        if self.realtime_chat_is_recording:
            self.realtime_chat_is_recording = False
            if self.realtime_chat_audio_timer:
                self.realtime_chat_audio_timer.stop()
                self.realtime_chat_audio_timer = None
            if hasattr(self, 'realtime_chat_stream') and self.realtime_chat_stream:
                self.realtime_chat_stream.stop_stream()
                self.realtime_chat_stream.close()
            if hasattr(self, 'realtime_chat_pyaudio') and self.realtime_chat_pyaudio:
                self.realtime_chat_pyaudio.terminate()
            self.realtime_chat_record_btn.setEnabled(True)
            self.realtime_chat_stop_record_btn.setEnabled(False)
            self.realtime_chat_processing_status.setText("录音已停止")
            self.realtime_chat_processing_status.setStyleSheet("color: red; font-weight: bold;")
            self.realtime_chat_add_message("录音已停止", "system")

    def realtime_chat_process_audio_data(self):
        """处理实时聊天音频数据"""
        if not self.realtime_chat_is_recording or not hasattr(self, 'realtime_chat_stream'):
            return

        # 如果正在处理上一段音频，不允许新录音
        if self.realtime_chat_is_processing:
            return

        try:
            # 从pyaudio流读取数据
            audio_bytes = self.realtime_chat_stream.read(self.realtime_chat_vad_config['chunk_size'], exception_on_overflow=False)

            if len(audio_bytes) > 0:
                # 计算RMS值用于VAD
                rms = self.realtime_chat_calculate_rms(audio_bytes)
                self.realtime_chat_update_vad_display(rms)

                # 简单的VAD逻辑
                is_speech = rms > self.realtime_chat_vad_config['vad_threshold']
                self.realtime_chat_update_voice_activity(is_speech)

                # 如果检测到语音，开始收集音频数据
                if is_speech:
                    self.realtime_chat_speech_frames.append(audio_bytes)
                    self.realtime_chat_silence_frames = 0
                else:
                    if self.realtime_chat_speech_frames:
                        self.realtime_chat_silence_frames += 1
                        # 如果静音持续时间超过阈值，发送已收集的音频
                        if self.realtime_chat_silence_frames >= self.realtime_chat_vad_config['max_silence_frames']:
                            self.realtime_chat_send_audio_chunk()

        except Exception as e:
            self.realtime_chat_add_message(f"音频处理错误: {str(e)}", "error")

    def realtime_chat_calculate_rms(self, audio_data):
        """计算实时聊天音频数据的RMS值"""
        if len(audio_data) == 0:
            return 0.0

        # 将字节数据转换为16位整数
        int16_array = []
        for i in range(0, len(audio_data), 2):
            if i + 1 < len(audio_data):
                # 小端字节序
                sample = int.from_bytes(audio_data[i:i+2], byteorder='little', signed=True)
                int16_array.append(sample)

        if not int16_array:
            return 0.0

        # 计算RMS
        sum_squares = sum(x * x for x in int16_array)
        rms = (sum_squares / len(int16_array)) ** 0.5

        # 归一化到0-1范围 (16位音频的最大值是32767)
        return rms / 32767.0

    def realtime_chat_update_vad_display(self, rms):
        """更新实时聊天VAD显示"""
        # 更新RMS显示
        self.realtime_chat_vad_rms.setText(f"RMS: {rms:.3f}")

        # 更新VAD仪表
        vad_level = min(int(rms * 100), 100)
        self.realtime_chat_vad_meter.setValue(vad_level)

        # 更新阈值显示
        threshold = self.realtime_chat_vad_config['vad_threshold']
        self.realtime_chat_vad_threshold.setText(f"阈值: {threshold:.3f}")

    def realtime_chat_update_voice_activity(self, is_active):
        """更新实时聊天语音活动指示器"""
        if is_active:
            self.realtime_chat_voice_indicator.setStyleSheet("color: #2ecc71; font-size: 20px;")
            self.realtime_chat_voice_status.setText("检测到语音")
        else:
            self.realtime_chat_voice_indicator.setStyleSheet("color: #bdc3c7; font-size: 20px;")
            self.realtime_chat_voice_status.setText("未检测到语音")

    def realtime_chat_send_audio_chunk(self):
        """发送实时聊天音频块到服务器"""
        if not self.realtime_chat_speech_frames or not self.realtime_chat_is_connected or self.realtime_chat_is_processing:
            return

        try:
            # 设置处理状态，防止新录音
            self.realtime_chat_is_processing = True
            self.realtime_chat_processing_status.setText("正在处理语音...")
            self.realtime_chat_processing_status.setStyleSheet("color: orange; font-weight: bold;")

            # 合并所有语音帧
            combined_audio = b''.join(self.realtime_chat_speech_frames)

            # 转换为base64
            base64_audio = base64.b64encode(combined_audio).decode('utf-8')

            # 发送到WebSocket
            message = json.dumps({
                "action": "audio",
                "data": {
                    "audio_data": base64_audio,
                    "format": "pcm"
                }
            })

            self.realtime_chat_websocket.sendTextMessage(message)
            self.realtime_chat_add_message("语音已发送，等待处理...", "system")

            # 清空已发送的帧
            self.realtime_chat_speech_frames.clear()
            self.realtime_chat_silence_frames = 0

        except Exception as e:
            self.realtime_chat_add_message(f"发送音频失败: {str(e)}", "error")
            self.realtime_chat_is_processing = False
            self.realtime_chat_processing_status.setText("等待语音输入")
            self.realtime_chat_processing_status.setStyleSheet("color: blue; font-weight: bold;")

    def realtime_chat_play_audio(self, audio_data):
        """将音频添加到实时聊天播放队列"""
        self.realtime_chat_audio_queue.append(audio_data)
        self.realtime_chat_play_next_audio()

    def realtime_chat_play_next_audio(self):
        """播放实时聊天队列中的下一个音频"""
        if self.realtime_chat_audio_queue and not self.realtime_chat_is_playing:
            try:
                audio_data = self.realtime_chat_audio_queue.pop(0)
                
                # 保存为临时WAV文件
                temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
                os.close(temp_fd)

                # 写入WAV数据
                with open(temp_path, 'wb') as f:
                    f.write(audio_data)

                # 使用QMediaPlayer播放
                if not hasattr(self, 'realtime_chat_audio_player'):
                    self.realtime_chat_audio_player = QMediaPlayer()
                    self.realtime_chat_audio_output = QAudioOutput()
                    self.realtime_chat_audio_player.setAudioOutput(self.realtime_chat_audio_output)

                self.realtime_chat_audio_player.setSource(QUrl.fromLocalFile(temp_path))
                self.realtime_chat_audio_player.play()
                self.realtime_chat_is_playing = True

                # 播放完成后清理临时文件
                self.realtime_chat_audio_player.mediaStatusChanged.connect(
                    lambda status: self.realtime_chat_on_audio_finished(temp_path) if status == QMediaPlayer.MediaStatus.EndOfMedia else None
                )

            except Exception as e:
                self.realtime_chat_add_message(f"播放音频失败: {e}", "error")
                self.realtime_chat_is_playing = False

    def realtime_chat_on_audio_finished(self, temp_path):
        """实时聊天音频播放完成"""
        self.realtime_chat_is_playing = False
        try:
            os.remove(temp_path)
        except:
            pass
        # 播放下一个音频
        self.realtime_chat_play_next_audio()

    def realtime_chat_add_message(self, message, msg_type, append=False):
        """添加实时聊天消息到记录"""
        timestamp = QTime.currentTime().toString("hh:mm:ss")

        if msg_type == "system":
            color = "#2ecc71"  # 绿色
            prefix = "🔧 系统"
        elif msg_type == "stt":
            color = "#3498db"  # 蓝色
            prefix = "🎤 STT"
        elif msg_type == "llm":
            color = "#9b59b6"  # 紫色
            prefix = "🤖 LLM"
        elif msg_type == "error":
            color = "#e74c3c"  # 红色
            prefix = "❌ 错误"
        else:
            color = "#34495e"  # 深灰色
            prefix = "💬 消息"

        formatted_message = f'<span style="color: {color};">[{timestamp}] {prefix}:</span> {message}<br>'

        if append and msg_type == "llm":
            # 对于LLM流式输出，追加到最后一条消息
            current_text = self.realtime_chat_text.toHtml()
            # 简单的追加逻辑，这里可以优化
            self.realtime_chat_text.setHtml(current_text + formatted_message)
        else:
            current_text = self.realtime_chat_text.toHtml()
            self.realtime_chat_text.setHtml(current_text + formatted_message)

        # 自动滚动到底部
        scrollbar = self.realtime_chat_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def realtime_chat_clear(self):
        """清空实时聊天记录"""
        self.realtime_chat_text.clear()
        self.realtime_chat_add_message("聊天记录已清空", "system")

    def realtime_chat_save(self):
        """保存实时聊天记录"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存聊天记录", "", "HTML文件 (*.html);;文本文件 (*.txt)"
            )

            if file_path:
                if file_path.endswith('.html'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(self.realtime_chat_text.toHtml())
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(self.realtime_chat_text.toPlainText())
                self.realtime_chat_add_message(f"聊天记录已保存到: {file_path}", "system")
        except Exception as e:
            self.realtime_chat_add_message(f"保存失败: {str(e)}", "error")