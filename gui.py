#!/usr/bin/env python3
"""
VOXELINK GUI 启动器

使用 PyQt6 创建的桌面 GUI，用于启动 VOXELINK 后端服务。
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
    QTextBrowser
)
from PyQt6.QtCore import QThread, pyqtSignal, QProcess, QUrl, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtWebSockets import QWebSocket
from PyQt6.QtNetwork import QAbstractSocket

# 添加backend目录到Python路径
backend_dir = Path(__file__).parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 添加backend/app目录到Python路径
app_dir = backend_dir / "app"
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))


class RecordingThread(QThread):
    """录音线程"""
    finished = pyqtSignal()

    def __init__(self, audio_stream, frames_list):
        super().__init__()
        self.audio_stream = audio_stream
        self.frames_list = frames_list
        self.is_recording = True

    def run(self):
        while self.is_recording:
            try:
                data = self.audio_stream.read(1024, exception_on_overflow=False)
                self.frames_list.append(data)
                self.msleep(10)  # 小延迟避免CPU占用过高
            except Exception as e:
                print(f"录音线程异常: {e}")
                break
        self.finished.emit()

    def stop_recording(self):
        """停止录音"""
        self.is_recording = False


class ServerThread(QThread):
    """后台运行服务器的线程"""
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, host, port, enable_stt, enable_tts, reload_mode):
        super().__init__()
        self.host = host
        self.port = port
        self.enable_stt = enable_stt
        self.enable_tts = enable_tts
        self.reload_mode = reload_mode
        self.process = None

    def run(self):
        try:
            # 构建命令
            cmd = [sys.executable, str(Path(__file__).parent / "start.py")]
            if self.enable_stt:
                cmd.append("--enable-stt")
            if self.enable_tts:
                cmd.append("--enable-tts")
            cmd.extend(["--host", self.host, "--port", str(self.port)])
            if self.reload_mode:
                cmd.append("--reload")

            self.output_signal.emit(f"🚀 启动命令: {' '.join(cmd)}")
            self.output_signal.emit("-" * 50)

            # 启动进程
            self.process = QProcess()
            self.process.setProgram(sys.executable)
            self.process.setArguments(cmd[1:])  # 去掉 sys.executable
            self.process.readyReadStandardOutput.connect(self.handle_output)
            self.process.readyReadStandardError.connect(self.handle_output)
            self.process.start()

            # 等待进程结束
            self.process.waitForFinished(-1)

        except Exception as e:
            self.output_signal.emit(f"❌ 启动失败: {str(e)}")
        finally:
            self.finished_signal.emit()

    def handle_output(self):
        if self.process:
            output = self.process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            error = self.process.readAllStandardError().data().decode('utf-8', errors='ignore')
            if output:
                self.output_signal.emit(output.strip())
            if error:
                self.output_signal.emit(f"错误: {error.strip()}")

    def stop(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
            self.process.waitForFinished(3000)


class VoxelinkGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.server_thread = None
        self.chat_websocket = None
        self.audio_player = None
        self.audio_output = None
        self.pyaudio_instance = None
        self.audio_stream = None
        self.recording_frames = []
        self.is_recording = False
        self.recorded_audio_file = None
        self.audio_queue = []
        self.is_playing = False
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

        chat_item = QListWidgetItem("💬 语音聊天")
        chat_item.setFont(QFont("Arial", 11))
        self.nav_list.addItem(chat_item)

        self.nav_list.currentRowChanged.connect(self.change_page)
        main_splitter.addWidget(self.nav_list)

        # 右侧内容区域
        self.stacked_widget = QStackedWidget()
        main_splitter.addWidget(self.stacked_widget)

        # 设置分割器比例
        main_splitter.setSizes([150, 850])

        # 创建启动管理页面
        self.create_server_page()

        # 创建聊天页面
        self.create_chat_page()

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
        self.host_input = QLineEdit("0.0.0.0")
        host_layout.addWidget(self.host_input)
        host_layout.addWidget(QLabel("端口:"))
        self.port_input = QLineEdit("8080")
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
        self.model_combo.addItems(["deepseek/deepseek-v3-0324", "gpt-3.5-turbo", "gpt-4"])
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
        url = f"ws://localhost:{port}/stt/ws/pipeline"
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

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.stop_server()
        self.disconnect_chat()

        # 清理录音资源
        self.cleanup_recording_resources()

        if self.recorded_audio_file and os.path.exists(self.recorded_audio_file):
            try:
                os.remove(self.recorded_audio_file)
            except:
                pass

        event.accept()


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