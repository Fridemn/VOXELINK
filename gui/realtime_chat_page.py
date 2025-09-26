#!/usr/bin/env python3
"""
VOXELINK GUI 实时语音聊天页面模块
"""

import json
import base64
import tempfile
import os
import re
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
        self.realtime_chat_pyaudio = None
        self.realtime_chat_stream = None
        self.realtime_chat_audio_timer = None
        self.realtime_chat_audio_queue = []
        self.realtime_chat_is_playing = False
        self.realtime_chat_current_llm_response = ""
        self.realtime_chat_is_streaming = False

        # 初始化音频播放状态到配置中
        if not hasattr(self.config, 'runtime_state'):
            self.config.runtime_state = type('RuntimeState', (), {})()
        if not hasattr(self.config.runtime_state, 'audio_playing'):
            self.config.runtime_state.audio_playing = False

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("🔄 VOXELINK 实时语音聊天")
        title_label.setObjectName("title_label")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 连接状态
        status_group = QGroupBox("连接状态")
        status_layout = QVBoxLayout(status_group)

        self.realtime_chat_status_label = QLabel("⚫ 未连接")
        self.realtime_chat_status_label.setObjectName("status_disconnected")
        status_layout.addWidget(self.realtime_chat_status_label)

        connect_layout = QHBoxLayout()
        self.realtime_chat_connect_btn = QPushButton("🔗 连接")
        self.realtime_chat_connect_btn.setObjectName("connect_button")
        self.realtime_chat_connect_btn.clicked.connect(self.connect)
        connect_layout.addWidget(self.realtime_chat_connect_btn)

        self.realtime_chat_disconnect_btn = QPushButton("⛔ 断开")
        self.realtime_chat_disconnect_btn.setObjectName("disconnect_button")
        self.realtime_chat_disconnect_btn.clicked.connect(self.disconnect)
        self.realtime_chat_disconnect_btn.setEnabled(False)
        connect_layout.addWidget(self.realtime_chat_disconnect_btn)

        status_layout.addLayout(connect_layout)
        layout.addWidget(status_group)

        # 实时控制
        control_group = QGroupBox("实时控制")
        control_layout = QVBoxLayout(control_group)

        # 录音控制
        record_layout = QHBoxLayout()
        self.realtime_chat_record_btn = QPushButton("🎤 开始实时录音")
        self.realtime_chat_record_btn.clicked.connect(self.start_recording)
        record_layout.addWidget(self.realtime_chat_record_btn)

        self.realtime_chat_stop_record_btn = QPushButton("⏹️ 停止录音")
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
        url = self.config['gui']['server']['realtime_chat_ws_url']
        self.realtime_chat_websocket.open(QUrl(url))

        self.realtime_chat_status_label.setText("🟡 连接中...")
        self.realtime_chat_status_label.setObjectName("status_connecting")

    def disconnect(self):
        """断开实时聊天WebSocket连接"""
        if self.realtime_chat_websocket and self.realtime_chat_is_connected:
            self.realtime_chat_websocket.close()
            self.realtime_chat_websocket = None
            self.realtime_chat_is_connected = False

        self.stop_recording()
        self.realtime_chat_status_label.setText("⚫ 已断开")
        self.realtime_chat_status_label.setObjectName("status_disconnected")
        self.realtime_chat_connect_btn.setEnabled(True)
        self.realtime_chat_disconnect_btn.setEnabled(False)
        self.realtime_chat_record_btn.setEnabled(False)

    def on_connected(self):
        """实时聊天WebSocket连接成功"""
        self.realtime_chat_is_connected = True
        self.realtime_chat_status_label.setText("🟢 已连接")
        self.realtime_chat_status_label.setObjectName("status_connected")
        self.realtime_chat_connect_btn.setEnabled(False)
        self.realtime_chat_disconnect_btn.setEnabled(True)
        self.realtime_chat_record_btn.setEnabled(True)
        self.add_message("实时聊天WebSocket连接成功", "system")

        # 连接成功后自动发送配置
        self.send_config()

    def on_disconnected(self):
        """实时聊天WebSocket断开连接"""
        self.realtime_chat_is_connected = False
        # 只更新UI状态，不要调用disconnect方法（避免递归）
        self.stop_recording()
        self.realtime_chat_status_label.setText("⚫ 已断开")
        self.realtime_chat_status_label.setObjectName("status_disconnected")
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
                    self.realtime_chat_current_llm_response = ""
                    self.realtime_chat_is_streaming = False

            elif msg_type == "stream_chunk":
                # 流式数据块
                chunk_data = data.get("data", {})

                if chunk_data.get("transcription"):
                    self.add_message(f"语音识别: {chunk_data['transcription']}", "stt")

                if chunk_data.get("text"):
                    self.realtime_chat_current_llm_response += chunk_data["text"]
                    
                    if not self.realtime_chat_is_streaming:
                        self.realtime_chat_is_streaming = True
                        self.add_message(self.realtime_chat_current_llm_response, "llm")
                    else:
                        self.replace_last_llm_message(self.realtime_chat_current_llm_response)

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
                self.add_message("处理完成", "system")
                self.realtime_chat_current_llm_response = ""
                self.realtime_chat_is_streaming = False

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

    def send_config(self):
        """发送实时聊天配置到服务器"""
        if not self.realtime_chat_websocket or self.realtime_chat_websocket.state() != QAbstractSocket.SocketState.ConnectedState:
            return

        config = {
            "model": self.config['gui']['models']['default_llm_model'],
            "stream": self.config['gui']['realtime_chat']['stream'],
            "tts": self.config['gui']['realtime_chat']['tts']
        }

        message = json.dumps({
            "action": "config",
            "data": config
        })
        self.realtime_chat_websocket.sendTextMessage(message)
        self.add_message("配置已发送", "system")

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

            # 重置音频帧缓冲区
            self.realtime_chat_speech_frames.clear()

            self.realtime_chat_record_btn.setEnabled(False)
            self.realtime_chat_stop_record_btn.setEnabled(True)
            self.realtime_chat_processing_status.setText("正在录音")
            self.realtime_chat_processing_status.setStyleSheet("color: green; font-weight: bold;")

            # 初始化PyAudio - 使用固定参数
            self.realtime_chat_pyaudio = pyaudio.PyAudio()
            self.realtime_chat_stream = self.realtime_chat_pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,  # 单声道
                rate=16000,  # 16kHz采样率
                input=True,
                frames_per_buffer=2048  # 固定缓冲区大小
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

            # 如果有累积的音频帧，发送出去
            if self.realtime_chat_speech_frames:
                self.add_message("录音停止，发送已录制的音频...", "system")
                self.send_audio_chunk()

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
            audio_bytes = self.realtime_chat_stream.read(2048, exception_on_overflow=False)

            if len(audio_bytes) > 0:
                # 累积音频数据到缓冲区
                self.realtime_chat_speech_frames.append(audio_bytes)

                # 检查是否达到发送阈值（例如：2秒的音频数据）
                max_frames = int(2.0 * 16000 / 2048)  # 基于固定参数计算
                if len(self.realtime_chat_speech_frames) >= max_frames:
                    self.send_audio_chunk()

        except Exception as e:
            self.add_message(f"音频处理错误: {str(e)}", "error")

    def send_pending_audio_chunk(self):
        """发送待处理的音频块"""
        # 这个方法目前简化实现，实际可以根据需要调整
        pass

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
                # 更新配置中的音频播放状态
                self.config.runtime_state.audio_playing = True

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
        # 更新配置中的音频播放状态
        self.config.runtime_state.audio_playing = False
        try:
            os.remove(temp_path)
        except:
            pass

        # 播放下一个音频
        self.play_next_audio()

        # 如果音频队列为空，说明整个TTS响应播放完成，重新启用录音
        if not self.realtime_chat_audio_queue:
            # 恢复UI状态
            self.realtime_chat_voice_indicator.setStyleSheet("color: #bdc3c7; font-size: 20px;")
            self.realtime_chat_voice_status.setText("未检测到语音")

    def add_message(self, message, msg_type, append=False):
        """添加实时聊天消息到记录"""
        timestamp = QTime.currentTime().toString("hh:mm:ss")

        if msg_type == "system":
            prefix = "🔧 系统"
        elif msg_type == "stt":
            prefix = "🎤 STT"
        elif msg_type == "llm":
            prefix = "🤖 LLM"
        elif msg_type == "error":
            prefix = "❌ 错误"
        else:
            prefix = "💬 消息"

        formatted_message = f'[{timestamp}] {prefix}: {message}'

        current_text = self.realtime_chat_text.toPlainText()
        if current_text:
            new_text = current_text + '\n' + formatted_message
        else:
            new_text = formatted_message
        
        self.realtime_chat_text.setPlainText(new_text)

        # 自动滚动到底部
        scrollbar = self.realtime_chat_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def add_stream_message(self, text):
        """添加流式消息并返回消息ID"""
        timestamp = QTime.currentTime().toString("hh:mm:ss")
        color = "#9b59b6"  # 紫色
        prefix = "🤖 LLM"

        formatted_message = f'<span style="color: {color};">[{timestamp}] {prefix}:</span> {text}<br>'

        current_text = self.realtime_chat_text.toHtml()
        self.realtime_chat_text.setHtml(current_text + formatted_message)

        return len(current_text)

    def update_stream_message(self, message_id, text):
        """更新流式消息内容"""
        timestamp = QTime.currentTime().toString("hh:mm:ss")
        color = "#9b59b6"  # 紫色
        prefix = "🤖 LLM"

        formatted_message = f'<span style="color: {color};">[{timestamp}] {prefix}:</span> {text}<br>'

        current_html = self.realtime_chat_text.toHtml()

        lines = current_html.split('<br>')
        if lines:
            lines[-2] = formatted_message.rstrip('<br>')
            new_html = '<br>'.join(lines)
            self.realtime_chat_text.setHtml(new_html)

    def replace_last_llm_message(self, new_text):
        """替换最后一条LLM消息的内容"""
        current_text = self.realtime_chat_text.toPlainText()

        lines = current_text.split('\n')
        last_llm_index = -1
        
        for i in range(len(lines) - 1, -1, -1):
            if '🤖 LLM:' in lines[i]:
                last_llm_index = i
                break
        
        if last_llm_index >= 0:
            line = lines[last_llm_index]
            prefix_end = line.find('🤖 LLM:') + len('🤖 LLM:')
            prefix = line[:prefix_end]
            
            lines[last_llm_index] = f'{prefix} {new_text}'
            
            new_content = '\n'.join(lines)
            self.realtime_chat_text.setPlainText(new_content)
            
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
                self, "保存聊天记录", "", "文本文件 (*.txt)"
            )

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.realtime_chat_text.toPlainText())
                self.add_message(f"聊天记录已保存到: {file_path}", "system")
        except Exception as e:
            self.add_message(f"保存失败: {str(e)}", "error")