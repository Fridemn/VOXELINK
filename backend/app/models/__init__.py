# app/models 包初始化

# 导入所有模型，确保 Tortoise ORM 能够正确注册
from .chat import ChatMessage, MessageRole

# 导出所有模型
__all__ = [
    "ChatMessage",
    "MessageRole",
]
