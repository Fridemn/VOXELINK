#!/usr/bin/env python3
"""
VOXELINK Live2D 模型显示页面

显示 Live2D 人物模型的页面。
"""

import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QScrollArea, QFrame
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import QTimerEvent, Qt
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import *
import live2d.v3 as live2d
from . import resources


class Live2DWidget(QOpenGLWidget):
    """Live2D渲染Widget"""

    def __init__(self, model_directory, model_file, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.model: live2d.LAppModel | None = None
        self.model_directory = model_directory
        self.model_file = model_file
        self.setMinimumSize(400, 500)

    def initializeGL(self) -> None:
        """初始化OpenGL"""
        # 初始化Live2D OpenGL
        live2d.glInit()

        # 创建模型
        self.model = live2d.LAppModel()

        # 加载模型
        model_path = os.path.join(resources.RESOURCES_DIRECTORY, self.model_directory, self.model_file)
        if os.path.exists(model_path):
            self.model.LoadModelJson(model_path)
        else:
            print(f"模型文件不存在: {model_path}")

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


class Live2DPage(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.model_directory = self.config.live2d.model_directory
        self.model_file = self.config.live2d.model_file
        self.live2d_widget = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题
        title_label = QLabel("🎭 Live2D 人物模型")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 模型信息
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Shape.Box)
        info_layout = QVBoxLayout(info_frame)

        model_name_label = QLabel(f"模型名称: {self.config.live2d.model_name}")
        model_name_label.setFont(QFont("Segoe UI", 12))
        info_layout.addWidget(model_name_label)

        model_path_label = QLabel(f"模型路径: {os.path.join(self.model_directory, self.model_file)}")
        model_path_label.setFont(QFont("Segoe UI", 10))
        model_path_label.setWordWrap(True)
        info_layout.addWidget(model_path_label)

        layout.addWidget(info_frame)

        # Live2D渲染区域
        try:
            # 初始化Live2D
            live2d.init()
            self.live2d_widget = Live2DWidget(self.model_directory, self.model_file)
            layout.addWidget(self.live2d_widget)
        except Exception as e:
            error_label = QLabel(f"Live2D初始化失败: {str(e)}")
            error_label.setStyleSheet("color: red;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

            # 回退到静态显示
            self.add_fallback_display(layout)

        # 控制按钮
        button_layout = QHBoxLayout()

        refresh_button = QPushButton("🔄 刷新")
        refresh_button.clicked.connect(self.refresh_display)
        button_layout.addWidget(refresh_button)

        if self.live2d_widget:
            reset_button = QPushButton("🏠 重置位置")
            reset_button.clicked.connect(self.reset_model)
            button_layout.addWidget(reset_button)

        layout.addLayout(button_layout)

    def add_fallback_display(self, layout):
        """添加静态显示作为回退方案"""
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # 加载纹理图像
        texture_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'live2d', self.model_directory, self.model_file.replace('.model3.json', '.4096'))
        if os.path.exists(texture_dir):
            texture_files = [f for f in os.listdir(texture_dir) if f.startswith('texture_') and f.endswith('.png')]
            for texture_file in sorted(texture_files):
                texture_path = os.path.join(texture_dir, texture_file)
                self.add_texture_display(scroll_layout, texture_file, texture_path)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

    def add_texture_display(self, layout, texture_name, texture_path):
        """添加纹理显示"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box)
        frame_layout = QVBoxLayout(frame)

        # 纹理名称
        name_label = QLabel(f"纹理: {texture_name}")
        name_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        frame_layout.addWidget(name_label)

        # 纹理图像
        pixmap = QPixmap(texture_path)
        if not pixmap.isNull():
            # 缩放图像以适应显示
            scaled_pixmap = pixmap.scaledToWidth(300, Qt.TransformationMode.SmoothTransformation)
            image_label = QLabel()
            image_label.setPixmap(scaled_pixmap)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_layout.addWidget(image_label)

            # 图像信息
            size_label = QLabel(f"尺寸: {pixmap.width()} x {pixmap.height()}")
            size_label.setFont(QFont("Segoe UI", 9))
            size_label.setStyleSheet("color: #666;")
            frame_layout.addWidget(size_label)
        else:
            error_label = QLabel("无法加载图像")
            error_label.setStyleSheet("color: red;")
            frame_layout.addWidget(error_label)

        layout.addWidget(frame)

    def refresh_display(self):
        """刷新显示"""
        # 重新初始化Live2D widget
        if self.live2d_widget:
            self.live2d_widget.close()
            self.live2d_widget = None

        # 清除布局中的Live2D widget
        layout = self.layout()
        if layout:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item.widget() and hasattr(item.widget(), 'model'):
                    layout.removeItem(item)
                    break

        # 重新添加Live2D widget
        try:
            live2d.init()
            self.live2d_widget = Live2DWidget(self.model_directory, self.model_file)
            layout.insertWidget(2, self.live2d_widget)  # 在info_frame之后插入
        except Exception as e:
            error_label = QLabel(f"Live2D初始化失败: {str(e)}")
            error_label.setStyleSheet("color: red;")
            error_label.setWordWrap(True)
            layout.insertWidget(2, error_label)

    def reset_model(self):
        """重置模型位置"""
        if self.live2d_widget and self.live2d_widget.model:
            # 重置拖拽状态
            self.live2d_widget.model.Drag(0, 0)

    def closeEvent(self, event):
        """关闭事件"""
        if self.live2d_widget:
            self.live2d_widget.close()
        super().closeEvent(event)
