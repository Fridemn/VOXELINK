#!/usr/bin/env python3
"""
VOXELINK Live2D 模块
"""

import os
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QScrollArea, QFrame, QMainWindow
from PyQt6.QtGui import QFont, QPixmap, QMouseEvent, QCursor
from PyQt6.QtCore import QTimerEvent, Qt, QPoint, QRect, QTimer
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import *
import live2d.v3 as live2d
from . import resources


class Live2DWidget(QOpenGLWidget):
    """Live2D渲染Widget"""

    def __init__(self, model_directory, model_file, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.model: live2d.LAppModel | None = None
        self.model_directory = model_directory
        self.model_file = model_file
        self.setFixedSize(400, 500)  # 确保大小固定

    def initializeGL(self) -> None:
        """初始化OpenGL"""
        try:
            # 初始化Live2D OpenGL
            live2d.glInit()

            # 创建模型
            self.model = live2d.LAppModel()

            # 加载模型
            model_path = os.path.join(resources.RESOURCES_DIRECTORY, self.model_directory, self.model_file)
            print(f"尝试加载Live2D模型: {model_path}")
            if os.path.exists(model_path):
                self.model.LoadModelJson(model_path)
                print("Live2D模型加载成功")
            else:
                print(f"模型文件不存在: {model_path}")
        except Exception as e:
            print(f"Live2D初始化失败: {str(e)}")
            import traceback
            traceback.print_exc()

        # 以 fps = 60 进行绘图
        self.startTimer(int(1000 / 60))

    def resizeGL(self, w: int, h: int) -> None:
        """调整窗口大小时调用"""
        if self.model:
            self.model.Resize(w, h)

    def paintGL(self) -> None:
        """绘制Live2D模型"""
        if self.model:
            # 清除缓冲区
            live2d.clearBuffer(0.0, 0.0, 0.0, 0.0)
            # 更新模型
            self.model.Update()
            # 绘制模型
            self.model.Draw()

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.model:
            x = event.position().x()
            y = event.position().y()
            self.model.Drag(x, y)

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if self.model:
            x = event.position().x()
            y = event.position().y()
            # 检查点击测试
            hit_areas = ["Body", "Head"]  # 可以根据模型配置调整
            for area in hit_areas:
                if self.model.HitTest(area, x, y):
                    print(f"点击了区域: {area}")
                    break

    def timerEvent(self, a0: QTimerEvent | None) -> None:
        """定时器事件，用于重绘"""
        self.update()


class DesktopPetWindow(QWidget):
    """Live2D桌宠窗口"""

    def __init__(self, config):
        super().__init__()
        print("初始化Live2D桌宠窗口...")
        self.config = config
        # 从配置中获取Live2D设置
        try:
            self.model_directory = getattr(self.config.live2d, 'model_dir', 'march7')
            self.model_file = '三月七.model3.json'  # 固定文件名
            self.model_name = getattr(self.config.live2d, 'model_display_name', '三月七 (March 7th)')
            print(f"模型目录: {self.model_directory}, 文件: {self.model_file}, 名称: {self.model_name}")
        except AttributeError:
            # 如果配置不存在，使用默认值
            self.model_directory = 'march7'
            self.model_file = '三月七.model3.json'
            self.model_name = '三月七 (March 7th)'
            print("使用默认配置")
        self.dragging = False
        self.drag_position = QPoint()

        self.init_ui()
        self.init_live2d()

        # 设置窗口属性 - 完全透明，无边框，鼠标事件穿透
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput  # 让鼠标事件穿透到下面的窗口
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)  # 移除系统背景
        self.setStyleSheet("background: transparent;")  # 设置透明背景

        # 设置窗口大小和位置 - 紧贴模型边缘
        self.setFixedSize(400, 500)  # 模型的实际渲染大小
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - 410, screen.height() - 510)  # 稍微调整位置

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 移除所有边距
        layout.setSpacing(0)

        # 直接添加Live2D渲染区域，不使用容器
        self.live2d_container = QWidget()
        self.live2d_container.setStyleSheet("background: transparent; border: none;")
        live2d_layout = QVBoxLayout(self.live2d_container)
        live2d_layout.setContentsMargins(0, 0, 0, 0)  # 移除所有边距
        live2d_layout.setSpacing(0)

        layout.addWidget(self.live2d_container)

        # 目光追踪定时器
        self.eye_tracking_timer = QTimer(self)
        self.eye_tracking_timer.timeout.connect(self.update_eye_tracking)
        self.eye_tracking_timer.start(50)  # 每50ms更新一次

    def init_live2d(self):
        """初始化Live2D"""
        try:
            # 初始化Live2D
            live2d.init()
            self.live2d_widget = Live2DWidget(self.model_directory, self.model_file)
            self.live2d_container.layout().addWidget(self.live2d_widget)
        except Exception as e:
            print(f"Live2D初始化失败: {str(e)}")
            # 回退到静态显示
            self.add_fallback_display()

    def add_fallback_display(self):
        """添加静态显示作为回退方案"""
        # 加载纹理图像
        texture_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'live2d', self.model_directory, self.model_file.replace('.model3.json', '.4096'))
        if os.path.exists(texture_dir):
            texture_files = [f for f in os.listdir(texture_dir) if f.startswith('texture_') and f.endswith('.png')]
            if texture_files:
                texture_path = os.path.join(texture_dir, sorted(texture_files)[0])
                pixmap = QPixmap(texture_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(350, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    image_label = QLabel()
                    image_label.setPixmap(scaled_pixmap)
                    image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.live2d_container.layout().addWidget(image_label)

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否点击在拖拽句柄上
            if self.drag_handle.geometry().contains(event.position().toPoint()):
                # 在拖拽句柄上，开始拖拽
                self.dragging = True
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
            elif self.live2d_widget and self.live2d_container.geometry().contains(event.position().toPoint()):
                # 在Live2D区域内，传递给模型
                local_pos = self.live2d_widget.mapFromGlobal(event.globalPosition().toPoint())
                if self.live2d_widget.rect().contains(local_pos):
                    fake_event = QMouseEvent(event.type(), local_pos, event.button(), event.buttons(), event.modifiers())
                    self.live2d_widget.mousePressEvent(fake_event)
                event.accept()
            else:
                # 在透明区域，忽略事件让它穿透
                event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件"""
        if self.dragging:
            # 拖拽中
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
        elif self.live2d_widget and self.live2d_container.geometry().contains(event.position().toPoint()):
            # 在Live2D区域内，传递给模型
            local_pos = self.live2d_widget.mapFromGlobal(event.globalPosition().toPoint())
            if self.live2d_widget.rect().contains(local_pos):
                fake_event = QMouseEvent(event.type(), local_pos, event.button(), event.buttons(), event.modifiers())
                self.live2d_widget.mouseMoveEvent(fake_event)
            event.accept()
        else:
            # 在透明区域，忽略事件
            event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.dragging:
                self.dragging = False
                event.accept()
            elif self.live2d_widget and self.live2d_container.geometry().contains(event.position().toPoint()):
                # 在Live2D区域内，传递给模型
                local_pos = self.live2d_widget.mapFromGlobal(event.globalPosition().toPoint())
                if self.live2d_widget.rect().contains(local_pos):
                    fake_event = QMouseEvent(event.type(), local_pos, event.button(), event.buttons(), event.modifiers())
                    self.live2d_widget.mouseReleaseEvent(fake_event)
                event.accept()
            else:
                # 在透明区域，忽略事件
                event.ignore()

    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        """关闭事件"""
        if self.live2d_widget:
            self.live2d_widget.close()
        super().closeEvent(event)

    def update_eye_tracking(self):
        """更新目光追踪"""
        if self.live2d_widget and self.live2d_widget.model:
            # 获取全局鼠标位置
            cursor_pos = QCursor.pos()

            # 将全局坐标转换为相对于桌宠窗口的坐标
            window_pos = self.mapFromGlobal(cursor_pos)

            # 将窗口坐标转换为Live2D模型的坐标
            # Live2D模型坐标系：左上角(0,0)，右下角(width,height)
            model_width = self.live2d_widget.width()
            model_height = self.live2d_widget.height()

            # 归一化坐标到模型尺寸，但允许一定范围外的跟踪
            x = window_pos.x()
            y = window_pos.y()

            # 限制在模型区域内，但允许一定范围外的跟踪
            x = max(-model_width * 0.5, min(model_width * 1.5, x))
            y = max(-model_height * 0.5, min(model_height * 1.5, y))

            # 调用Live2D的Drag方法来更新注视方向
            self.live2d_widget.model.Drag(x, y)


def start_desktop_pet(config):
    """启动Live2D桌宠"""
    print("启动Live2D桌宠...")
    app = QApplication.instance()
    if app is None:
        # 如果QApplication不存在，创建一个新的
        from PyQt6.QtCore import Qt
        try:
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        except AttributeError:
            pass

        app = QApplication(sys.argv)
        try:
            app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        except AttributeError:
            pass

    pet_window = DesktopPetWindow(config)
    print("桌宠窗口已创建，正在显示...")
    pet_window.show()
    print("桌宠窗口显示完成")

    return pet_window