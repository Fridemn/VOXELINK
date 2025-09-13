"""
app/config/app_config.py
应用全局配置管理模块。
"""

from typing import Any
from loguru import logger

from .default import DEFAULT_CONFIG


class AppConfig(dict):
    """从环境变量读取的配置，支持直接通过点号操作符访问根配置项"""

    def __init__(self):
        super().__init__()

        # 直接使用从环境变量读取的默认配置
        self.update(DEFAULT_CONFIG)
        logger.info("Configuration loaded")

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as e:
            raise AttributeError(f"Configuration key '{key}' not found") from e

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value
