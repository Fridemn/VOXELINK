#!/usr/bin/env python3
"""
VOXELINK GUI 配置文件管理页面模块
"""

import json
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton, QGroupBox, QScrollArea, QSpinBox, QDoubleSpinBox
from PyQt6.QtGui import QFont


class ConfigPage(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.config_data = {}
        self.config_widgets = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

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
            print("配置已保存")
        except Exception as e:
            print(f"保存配置失败: {e}")

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