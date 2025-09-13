"""
app/utils/logger.py
基于loguru的简化日志管理工具。
- 提供统一的日志配置和格式化。
"""

from loguru import logger


def setup_logger():
    """配置loguru日志器"""
    # 移除默认handler
    logger.remove()

    # 添加控制台输出
    logger.add(
        sink=lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> <level>[{level}]</level> <cyan>{name}</cyan>: <level>{message}</level>",
        level="DEBUG",
        colorize=True,
    )

    # 添加文件输出
    logger.add(
        "logs/app-{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} [{level}] {name}: {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )
