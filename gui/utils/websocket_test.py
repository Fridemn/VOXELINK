#!/usr/bin/env python3
"""
VOXELINK WebSocket连接测试工具模块
"""

import re
from PyQt6.QtCore import QTimer, QUrl, QObject, pyqtSignal
from PyQt6.QtWebSockets import QWebSocket
from PyQt6.QtNetwork import QAbstractSocket


class WebSocketTester(QObject):
    """WebSocket连接测试器"""

    test_completed = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, ws_url, timeout=20000):
        super().__init__()
        self.ws_url = ws_url
        self.timeout = timeout
        self.websocket = None
        self.timer = None

    def __del__(self):
        """析构函数，确保资源被正确清理"""
        try:
            self.cleanup()
        except:
            pass

    def start_test(self):
        """开始WebSocket连接测试"""
        try:
            # 清理之前的测试连接
            self.cleanup()

            # 创建测试WebSocket连接
            self.websocket = QWebSocket()
            self.websocket.connected.connect(self.on_connected)
            self.websocket.disconnected.connect(self.on_disconnected)
            self.websocket.errorOccurred.connect(self.on_error)

            # 设置超时
            self.timer = QTimer()
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.on_timeout)
            self.timer.start(self.timeout)

            # 连接到WebSocket URL
            self.websocket.open(QUrl(self.ws_url))

        except Exception as e:
            self.test_completed.emit(False, f"WebSocket测试初始化失败: {str(e)}")
            self.cleanup()

    def on_connected(self):
        """WebSocket连接成功"""
        try:
            # 不立即发送成功信号，延迟2秒后发送，让后端加载消息先显示
            QTimer.singleShot(2000, self.show_success_message)

            # 立即断开连接
            if self.websocket and self.websocket.state() == QAbstractSocket.SocketState.ConnectedState:
                self.websocket.close()

        except Exception as e:
            self.test_completed.emit(False, f"测试连接处理异常: {str(e)}")
            self.cleanup()

    def show_success_message(self):
        """显示WebSocket测试成功消息"""
        self.test_completed.emit(True, "WebSocket连接成功")

    def on_disconnected(self):
        """WebSocket连接断开"""
        # 清理资源
        self.cleanup()

    def on_error(self, error):
        """WebSocket连接错误"""
        try:
            error_msg = "未知错误"
            if self.websocket:
                try:
                    error_msg = self.websocket.errorString()
                except:
                    error_msg = "获取错误信息失败"
            self.test_completed.emit(False, f"WebSocket连接失败: {error_msg}")
        except Exception as e:
            self.test_completed.emit(False, f"WebSocket错误处理异常: {str(e)}")
        finally:
            self.cleanup()

    def on_timeout(self):
        """WebSocket测试超时"""
        try:
            # 尝试关闭连接
            if self.websocket and self.websocket.state() != QAbstractSocket.SocketState.UnconnectedState:
                self.websocket.close()
            self.test_completed.emit(False, "WebSocket连接测试超时")
        except Exception as e:
            self.test_completed.emit(False, f"超时处理异常: {str(e)}")
        finally:
            self.cleanup()

    def cleanup(self):
        """清理WebSocket测试资源"""
        try:
            # 先停止定时器
            if self.timer:
                self.timer.stop()
                self.timer.deleteLater()
                self.timer = None

            # 清理WebSocket连接
            if self.websocket:
                # 先断开信号连接，避免在销毁过程中触发回调
                try:
                    self.websocket.blockSignals(True)  # 阻止所有信号
                except:
                    pass

                # 关闭连接
                try:
                    if self.websocket.state() != QAbstractSocket.SocketState.UnconnectedState:
                        self.websocket.close()
                except:
                    pass

                # 标记对象为待删除并清除引用
                try:
                    self.websocket.deleteLater()
                except:
                    pass

                self.websocket = None

        except Exception as e:
            # 记录错误但不抛出，避免GUI崩溃
            print(f"清理WebSocket测试资源时出错: {e}")
            # 强制清理引用
            self.websocket = None
            self.timer = None