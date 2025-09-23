"""
app包初始化。
- 加载全局配置、日志等核心资源。
- 供其他模块统一引用。
"""

from .config.app_config import AppConfig
from .utils.logger import setup_logger

setup_logger()

# 初始化全局配置实例
app_config = AppConfig()

__all__ = [
    "app_config",
]
