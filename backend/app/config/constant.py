"""
app/config/constant.py
全局常量定义。
- 包含配置路径、默认值映射等。
- 从 config.json 读取可配置的常量。
"""

import os


DEFAULT_VALUE_MAP = {
    "int": 0,
    "float": 0.0,
    "bool": False,
    "string": "",
    "text": "",
    "list": [],
    "object": {},
}
