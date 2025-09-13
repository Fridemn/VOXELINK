"""
app/config/constant.py
全局常量定义。
- 包含配置路径、默认值映射等。
- 从环境变量读取可配置的常量。
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)


DEFAULT_VALUE_MAP = {
    "int": 0,
    "float": 0.0,
    "bool": False,
    "string": "",
    "text": "",
    "list": [],
    "object": {},
}
