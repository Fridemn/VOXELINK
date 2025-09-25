#!/usr/bin/env python3
"""
VOXELINK Live2D 模块
"""

import os
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QScrollArea, QFrame, QMainWindow
from PyQt6.QtGui import QFont, QPixmap, QMouseEvent, QCursor
from PyQt6.QtCore import QTimerEvent, Qt, QPoint, QPointF, QRect, QTimer
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import *
import live2d.v3 as live2d
from . import resources

# Windows API for mouse pass-through
try:
    import ctypes
    from ctypes import wintypes
    
    # Windows constants
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_LAYERED = 0x00080000
    
    # Windows API functions
    user32 = ctypes.windll.user32
    GetWindowLong = user32.GetWindowLongW
    SetWindowLong = user32.SetWindowLongW
    
    WINDOWS_API_AVAILABLE = True
except ImportError:
    WINDOWS_API_AVAILABLE = False
    print("Windows API不可用，使用备用方案")


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
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if self.model and event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            y = event.position().y()
            # 检查释放时的hit test
            hit_areas = ["Body", "Head", "Face"]
            for area in hit_areas:
                try:
                    if self.model.HitTest(area, x, y):
                        print(f"在{area}区域释放鼠标")
                        # 可以在这里添加特定的交互逻辑
                        break
                except:
                    continue

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
    
    def is_hit_at_point(self, x, y):
        """检查指定坐标是否命中模型（用于透明度检测）"""
        if not self.model:
            return False
        
        # 检查多个可能的hit区域
        hit_areas = ["Body", "Head", "Face", "Hair", "Outfit", "Accessory", "Model"]
        for area in hit_areas:
            try:
                if self.model.HitTest(area, x, y):
                    return True
            except:
                continue  # 如果某个区域不存在，继续检查下一个
        
        return False

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

        self.init_ui()
        self.init_live2d()

        # 设置窗口属性 - 完全透明，无边框
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
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
        
        # 添加鼠标跟踪以实现悬停效果
        self.setMouseTracking(True)
        if hasattr(self, 'live2d_widget'):
            self.live2d_widget.setMouseTracking(True)
        
        # 鼠标穿透状态控制
        self.mouse_transparent = False
        self.last_mouse_pos = QPoint(0, 0)
        
        # 创建定时器来检查鼠标位置并动态切换穿透状态
        self.transparency_timer = QTimer(self)
        self.transparency_timer.timeout.connect(self.update_mouse_transparency)
        self.transparency_timer.start(50)  # 每50ms检查一次
        
    def update_mouse_transparency(self):
        """根据鼠标当前位置动态更新穿透状态"""
        try:
            # 获取全局鼠标位置
            global_mouse_pos = QCursor.pos()
            # 转换为窗口相对位置
            local_mouse_pos = self.mapFromGlobal(global_mouse_pos)
            
            # 检查鼠标是否在窗口内
            if not self.rect().contains(local_mouse_pos):
                # 鼠标在窗口外，启用穿透
                if not self.mouse_transparent:
                    self.set_mouse_transparent(True)
                return
            
            # 检查当前位置是否应该透明
            should_be_transparent = self.is_transparent_at_point(local_mouse_pos)
            
            # 如果状态需要改变，则更新
            if should_be_transparent != self.mouse_transparent:
                self.set_mouse_transparent(should_be_transparent)
                
        except Exception as e:
            print(f"更新透明度状态时出错: {e}")
    
    def set_mouse_transparent(self, transparent):
        """设置鼠标穿透状态"""
        if WINDOWS_API_AVAILABLE:
            hwnd = int(self.winId())
            current_style = GetWindowLong(hwnd, GWL_EXSTYLE)
            
            if transparent:
                # 启用鼠标穿透
                new_style = current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED
            else:
                # 禁用鼠标穿透
                new_style = current_style & ~WS_EX_TRANSPARENT
            
            SetWindowLong(hwnd, GWL_EXSTYLE, new_style)
            self.mouse_transparent = transparent
            print(f"鼠标穿透状态: {'启用' if transparent else '禁用'}")
        else:
            print("Windows API不可用，无法设置鼠标穿透")

    def init_live2d(self):
        """初始化Live2D"""
        try:
            # 初始化Live2D
            live2d.init()
            self.live2d_widget = Live2DWidget(self.model_directory, self.model_file)
            self.live2d_widget.setMouseTracking(True)  # 启用鼠标跟踪
            self.live2d_container.layout().addWidget(self.live2d_widget)
        except Exception as e:
            print(f"Live2D初始化失败: {str(e)}")
            # 回退到静态显示
            self.add_fallback_display()

    def is_transparent_at_point(self, pos):
        """检测指定位置是否为透明像素"""
        try:
            # 如果有Live2D模型，检查是否在模型渲染区域内
            if self.live2d_widget and hasattr(self.live2d_widget, 'model') and self.live2d_widget.model:
                # 检查是否在Live2D widget区域内
                widget_rect = self.live2d_widget.geometry()
                if widget_rect.contains(pos):
                    # 转换为Live2D widget内的坐标
                    local_pos = pos - widget_rect.topLeft()
                    
                    # 使用Live2D的精确hit test来检测是否点击到模型
                    if self.live2d_widget.is_hit_at_point(local_pos.x(), local_pos.y()):
                        return False  # 点击到模型，不透明
                    
                    # 如果Live2D hit test失败，使用简单的几何边界检查作为备选
                    # 假设模型在widget的中心区域内
                    center_x = widget_rect.width() // 2
                    center_y = widget_rect.height() // 2
                    model_width = widget_rect.width() * 0.6  # 假设模型占60%宽度
                    model_height = widget_rect.height() * 0.8  # 假设模型占80%高度
                    
                    # 椭圆边界检查（更贴近人形模型的形状）
                    dx = (local_pos.x() - center_x) / (model_width // 2)
                    dy = (local_pos.y() - center_y) / (model_height // 2)
                    
                    is_in_model = dx * dx + dy * dy <= 1.0
                    
                    # 调试信息
                    print(f"位置检测: pos={pos}, local={local_pos}, 椭圆检测={'在模型内' if is_in_model else '在模型外'}")
                    
                    if is_in_model:
                        return False  # 在模型的椭圆边界内，不透明
            
            return True  # 其他区域透明
        except Exception as e:
            print(f"透明度检测错误: {e}")
            return True  # 出错时默认透明
    
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
        pos = event.position().toPoint()
        
        if event.button() == Qt.MouseButton.LeftButton:
            if self.live2d_widget:
                # 检查是否在模型区域内
                widget_rect = self.live2d_widget.geometry()
                if widget_rect.contains(pos):
                    local_pos = pos - widget_rect.topLeft()
                    
                    # 传递给Live2D模型处理点击
                    fake_event = QMouseEvent(event.type(), 
                                           QPointF(local_pos.x(), local_pos.y()),
                                           event.button(), event.buttons(), event.modifiers())
                    self.live2d_widget.mousePressEvent(fake_event)
                    
                event.accept()
                return
        
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件"""
        pos = event.position().toPoint()
        
        # 设置光标
        if not self.is_transparent_at_point(pos):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        
        # 传递给Live2D模型
        if self.live2d_widget:
            widget_rect = self.live2d_widget.geometry()
            if widget_rect.contains(pos):
                local_pos = pos - widget_rect.topLeft()
                fake_event = QMouseEvent(event.type(), 
                                       QPointF(local_pos.x(), local_pos.y()),
                                       event.button(), event.buttons(), event.modifiers())
                self.live2d_widget.mouseMoveEvent(fake_event)
        
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        pos = event.position().toPoint()
        
        if event.button() == Qt.MouseButton.LeftButton:
            # 传递给Live2D模型
            if self.live2d_widget:
                widget_rect = self.live2d_widget.geometry()
                if widget_rect.contains(pos):
                    local_pos = pos - widget_rect.topLeft()
                    fake_event = QMouseEvent(event.type(), 
                                           QPointF(local_pos.x(), local_pos.y()),
                                           event.button(), event.buttons(), event.modifiers())
                    self.live2d_widget.mouseReleaseEvent(fake_event)
        
        event.accept()

    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_T and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Ctrl+T 测试透明度检测
            cursor_pos = QCursor.pos()
            local_pos = self.mapFromGlobal(cursor_pos)
            is_transparent = self.is_transparent_at_point(local_pos)
            print(f"当前鼠标位置 {local_pos} 透明度检测结果: {'透明' if is_transparent else '不透明'}")
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