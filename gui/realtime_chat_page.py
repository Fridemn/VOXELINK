#!/usr/bin/env python3
"""
VOXELINK GUI 实时语音聊天页面模块
"""

import json
import base64
import tempfile
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton, QTextEdit, QGroupBox, QComboBox, QProgressBar, QTextBrowser
from PyQt6.QtCore import QTimer, QTime, QUrl
from PyQt6.QtGui import QFont
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtWebSockets import QWebSocket
from PyQt6.QtNetwork import QAbstractSocket


class RealtimeChatPage(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.realtime_chat_websocket = None
        self.realtime_chat_is_connected = False
        self.realtime_chat_is_recording = False
        self.realtime_chat_is_processing = False
        self.realtime_chat_speech_frames = []
        self.realtime_chat_silence_frames = 0
        self.realtime_chat_pyaudio = None
        self.realtime_chat_stream = None
        self.realtime_chat_audio_timer = None
        self.realtime_chat_audio_queue = []
        self.realtime_chat_is_playing = False
        self.realtime_chat_vad_config = self.config['gui']['vad']['realtime_chat']
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

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
        self.realtime_chat_connect_btn.clicked.connect(self.connect)
        connect_layout.addWidget(self.realtime_chat_connect_btn)

        self.realtime_chat_disconnect_btn = QPushButton("断开")
        self.realtime_chat_disconnect_btn.clicked.connect(self.disconnect)
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
        self.realtime_chat_update_config_btn.clicked.connect(self.update_config)
        config_layout.addWidget(self.realtime_chat_update_config_btn)

        layout.addWidget(config_group)

        # 实时控制
        control_group = QGroupBox("实时控制")
        control_layout = QVBoxLayout(control_group)

        # 录音控制
        record_layout = QHBoxLayout()
        self.realtime_chat_record_btn = QPushButton("开始实时录音")
        self.realtime_chat_record_btn.clicked.connect(self.start_recording)
        record_layout.addWidget(self.realtime_chat_record_btn)

        self.realtime_chat_stop_record_btn = QPushButton("停止录音")
        self.realtime_chat_stop_record_btn.clicked.connect(self.stop_recording)
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
        self.realtime_chat_clear_btn.clicked.connect(self.clear)
        clear_chat_layout.addWidget(self.realtime_chat_clear_btn)

        self.realtime_chat_save_btn = QPushButton("保存记录")
        self.realtime_chat_save_btn.clicked.connect(self.save)
        clear_chat_layout.addWidget(self.realtime_chat_save_btn)

        chat_layout.addLayout(clear_chat_layout)
        layout.addWidget(chat_group)

    def connect(self):
        """连接到实时聊天WebSocket"""
        # 如果已经连接，先断开
        if self.realtime_chat_is_connected:
            self.disconnect()

        # 创建新的WebSocket
        self.realtime_chat_websocket = QWebSocket()
        self.realtime_chat_websocket.connected.connect(self.on_connected)
        self.realtime_chat_websocket.disconnected.connect(self.on_disconnected)
        self.realtime_chat_websocket.textMessageReceived.connect(self.on_message)
        self.realtime_chat_websocket.binaryMessageReceived.connect(self.on_binary_message)

        # 连接到自动pipeline WebSocket
        url = self.config['gui']['server']['auto_pipeline_ws_url']
        self.realtime_chat_websocket.open(QUrl(url))

        self.realtime_chat_status_label.setText("连接中...")
        self.realtime_chat_status_label.setStyleSheet("color: orange; font-weight: bold;")

    def disconnect(self):
        """断开实时聊天WebSocket连接"""
        if self.realtime_chat_websocket and self.realtime_chat_is_connected:
            self.realtime_chat_websocket.close()
            self.realtime_chat_websocket = None
            self.realtime_chat_is_connected = False

        self.stop_recording()
        self.realtime_chat_status_label.setText("已断开")
        self.realtime_chat_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.realtime_chat_connect_btn.setEnabled(True)
        self.realtime_chat_disconnect_btn.setEnabled(False)
        self.realtime_chat_record_btn.setEnabled(False)

    def on_connected(self):
        """实时聊天WebSocket连接成功"""
        self.realtime_chat_is_connected = True
        self.realtime_chat_status_label.setText("已连接")
        self.realtime_chat_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.realtime_chat_connect_btn.setEnabled(False)
        self.realtime_chat_disconnect_btn.setEnabled(True)
        self.realtime_chat_record_btn.setEnabled(True)
        self.add_message("实时聊天WebSocket连接成功", "system")

        # 连接成功后自动发送配置
        self.update_config()

    def on_disconnected(self):
        """实时聊天WebSocket断开连接"""
        self.realtime_chat_is_connected = False
        # 只更新UI状态，不要调用disconnect方法（避免递归）
        self.stop_recording()
        self.realtime_chat_status_label.setText("已断开")
        self.realtime_chat_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.realtime_chat_connect_btn.setEnabled(True)
        self.realtime_chat_disconnect_btn.setEnabled(False)
        self.realtime_chat_record_btn.setEnabled(False)
        self.add_message("连接已断开", "system")

    def on_message(self, message):
        """接收实时聊天文本消息"""
        try:
            data = json.loads(message)
            self.handle_message(data)
        except json.JSONDecodeError:
            print(f"收到无效JSON消息: {message}")

    def on_binary_message(self, message):
        """接收实时聊天二进制消息（音频数据）"""
        # 处理TTS音频数据
        self.realtime_chat_audio_queue.append(message)
        self.play_next_audio()

    def handle_message(self, data):
        """处理实时聊天消息"""
        if data.get("success"):
            if data.get("message"):
                # 连接或配置消息
                self.add_message(data['message'], "system")
                return

            msg_type = data.get("type", "")

            if msg_type == "stt_result":
                # STT结果
                stt_data = data.get("data", {})
                if stt_data.get("transcription"):
                    self.add_message(f"语音识别: {stt_data['transcription']}", "stt")
                    self.add_message("正在生成回复...", "system")

            elif msg_type == "stream_chunk":
                # 流式数据块
                chunk_data = data.get("data", {})

                if chunk_data.get("transcription"):
                    self.add_message(f"语音识别: {chunk_data['transcription']}", "stt")

                if chunk_data.get("text"):
                    self.add_message(chunk_data["text"], "llm", append=True)

                if chunk_data.get("audio"):
                    # 解码base64音频并添加到队列
                    audio_data = base64.b64decode(chunk_data["audio"])
                    self.realtime_chat_audio_queue.append(audio_data)
                    self.play_next_audio()

            elif msg_type == "response":
                # 非流式响应
                response_data = data.get("data", {})

                if response_data.get("response_text"):
                    self.add_message(response_data["response_text"], "llm")

                if response_data.get("audio"):
                    audio_data = base64.b64decode(response_data["audio"])
                    self.realtime_chat_audio_queue.append(audio_data)
                    self.play_next_audio()

            elif msg_type == "complete":
                # 处理完成
                self.add_message("处理完成", "system")

            # 处理完成后允许再次录音
            if msg_type in ["stt_result", "response", "complete"]:
                self.realtime_chat_is_processing = False
                self.realtime_chat_processing_status.setText("等待语音输入")
                self.realtime_chat_processing_status.setStyleSheet("color: blue; font-weight: bold;")
        else:
            # 错误消息
            error_msg = data.get("error", "未知错误")
            self.add_message(f"处理失败: {error_msg}", "error")
            self.realtime_chat_is_processing = False
            self.realtime_chat_processing_status.setText("等待语音输入")
            self.realtime_chat_processing_status.setStyleSheet("color: blue; font-weight: bold;")

    def update_config(self):
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
        self.add_message("配置已更新", "system")

    def start_recording(self):
        """开始实时录音"""
        if not self.realtime_chat_websocket or self.realtime_chat_websocket.state() != QAbstractSocket.SocketState.ConnectedState:
            self.add_message("请先连接到服务器", "error")
            return

        try:
            import pyaudio

            self.add_message("开始实时录音...", "system")
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
            self.realtime_chat_audio_timer.timeout.connect(self.process_audio_data)
            self.realtime_chat_audio_timer.start(100)  # 每100ms读取一次
            self.add_message("音频录制已启动", "system")

        except Exception as e:
            self.add_message(f"录音失败: {str(e)}", "error")
            self.realtime_chat_is_recording = False
            self.realtime_chat_record_btn.setEnabled(True)
            self.realtime_chat_stop_record_btn.setEnabled(False)

    def stop_recording(self):
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
            self.add_message("录音已停止", "system")

    def process_audio_data(self):
        """处理实时聊天音频数据"""
        if not self.realtime_chat_is_recording or not hasattr(self, 'realtime_chat_stream'):
            return

        # 如果正在处理上一段音频，不允许新录音
        if self.realtime_chat_is_processing:
            return

        try:
            import pyaudio

            # 从pyaudio流读取数据
            audio_bytes = self.realtime_chat_stream.read(self.realtime_chat_vad_config['chunk_size'], exception_on_overflow=False)

            if len(audio_bytes) > 0:
                # 计算RMS值用于VAD
                rms = self.calculate_rms(audio_bytes)
                self.update_vad_display(rms)

                # 简单的VAD逻辑
                is_speech = rms > self.realtime_chat_vad_config['vad_threshold']
                self.update_voice_activity(is_speech)

                # 如果检测到语音，开始收集音频数据
                if is_speech:
                    self.realtime_chat_speech_frames.append(audio_bytes)
                    self.realtime_chat_silence_frames = 0
                else:
                    if self.realtime_chat_speech_frames:
                        self.realtime_chat_silence_frames += 1
                        # 如果静音持续时间超过阈值，发送已收集的音频
                        if self.realtime_chat_silence_frames >= self.realtime_chat_vad_config['max_silence_frames']:
                            self.send_audio_chunk()

        except Exception as e:
            self.add_message(f"音频处理错误: {str(e)}", "error")

    def calculate_rms(self, audio_data):
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

    def update_vad_display(self, rms):
        """更新实时聊天VAD显示"""
        # 更新RMS显示
        self.realtime_chat_vad_rms.setText(f"RMS: {rms:.3f}")

        # 更新VAD仪表
        vad_level = min(int(rms * 100), 100)
        self.realtime_chat_vad_meter.setValue(vad_level)

        # 更新阈值显示
        threshold = self.realtime_chat_vad_config['vad_threshold']
        self.realtime_chat_vad_threshold.setText(f"阈值: {threshold:.3f}")

    def update_voice_activity(self, is_active):
        """更新实时聊天语音活动指示器"""
        if is_active:
            self.realtime_chat_voice_indicator.setStyleSheet("color: #2ecc71; font-size: 20px;")
            self.realtime_chat_voice_status.setText("检测到语音")
        else:
            self.realtime_chat_voice_indicator.setStyleSheet("color: #bdc3c7; font-size: 20px;")
            self.realtime_chat_voice_status.setText("未检测到语音")

    def send_audio_chunk(self):
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
            self.add_message("语音已发送，等待处理...", "system")

            # 清空已发送的帧
            self.realtime_chat_speech_frames.clear()
            self.realtime_chat_silence_frames = 0

        except Exception as e:
            self.add_message(f"发送音频失败: {str(e)}", "error")
            self.realtime_chat_is_processing = False
            self.realtime_chat_processing_status.setText("等待语音输入")
            self.realtime_chat_processing_status.setStyleSheet("color: blue; font-weight: bold;")

    def play_next_audio(self):
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
                    lambda status: self.on_audio_finished(temp_path) if status == QMediaPlayer.MediaStatus.EndOfMedia else None
                )

            except Exception as e:
                self.add_message(f"播放音频失败: {e}", "error")
                self.realtime_chat_is_playing = False

    def on_audio_finished(self, temp_path):
        """实时聊天音频播放完成"""
        self.realtime_chat_is_playing = False
        try:
            os.remove(temp_path)
        except:
            pass
        # 播放下一个音频
        self.play_next_audio()

    def add_message(self, message, msg_type, append=False):
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

    def clear(self):
        """清空实时聊天记录"""
        self.realtime_chat_text.clear()
        self.add_message("聊天记录已清空", "system")

    def save(self):
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
                self.add_message(f"聊天记录已保存到: {file_path}", "system")
        except Exception as e:
            self.add_message(f"保存失败: {str(e)}", "error")