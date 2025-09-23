"""
app包初始化。
- 加载全局配置、日志等核心资源。
- 供其他模块统一引用。
"""

from .config.app_config import AppConfig
from .utils.logger import setup_logger

# 延迟创建app_config实例，避免循环导入
def get_app_config():
    if not hasattr(get_app_config, '_instance'):
        get_app_config._instance = AppConfig()
    return get_app_config._instance

setup_logger()

# 为了向后兼容，提供app_config，但延迟初始化
app_config = None

__all__ = [
    "app_config",
    "get_app_config",
]
