#!/usr/bin/env python3
"""
VOXELINK GUI 线程模块

包含录音和服务器启动的线程类。
"""

import sys
import os
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal, QProcess


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

    def __init__(self, host, port, enable_stt, enable_tts):
        super().__init__()
        self.host = host
        self.port = port
        self.enable_stt = enable_stt
        self.enable_tts = enable_tts
        self.process = None

    def run(self):
        try:
            # 添加Python路径
            backend_dir = Path(__file__).parent.parent / "backend"
            app_dir = backend_dir / "app"
            pythonpath = os.environ.get('PYTHONPATH', '')
            if pythonpath:
                pythonpath = f"{str(app_dir)};{str(backend_dir)};{pythonpath}"
            else:
                pythonpath = f"{str(app_dir)};{str(backend_dir)}"
            os.environ['PYTHONPATH'] = pythonpath

            # 构建命令
            cmd = [sys.executable, str(Path(__file__).parent.parent / "start.py")]
            if self.enable_stt:
                cmd.append("--enable-stt")
            if self.enable_tts:
                cmd.append("--enable-tts")
            cmd.extend(["--host", self.host, "--port", str(self.port)])

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
                self.output_signal.emit(f"{error.strip()}")

    def stop(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()