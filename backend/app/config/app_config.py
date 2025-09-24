"""
app/config/app_config.py
应用全局配置管理模块。
"""

from typing import Any
from loguru import logger

from .default import DEFAULT_CONFIG


class AppConfig(dict):
    """从环境变量读取的配置，支持直接通过点号操作符访问根配置项"""

    def __init__(self, data=None):
        super().__init__()
        if data is None:
            data = DEFAULT_CONFIG
        self._convert_dict(data)
        if data is DEFAULT_CONFIG:
            logger.info("Configuration loaded")

    def _convert_dict(self, data):
        """递归转换嵌套字典为AppConfig实例"""
        for key, value in data.items():
            if isinstance(value, dict):
                self[key] = AppConfig(value)
            else:
                self[key] = value

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as e:
            raise AttributeError(f"Configuration key '{key}' not found") from e

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value
