"""
app/models/chat.py
聊天消息数据模型。
- 定义消息类型、角色、消息ORM模型。
- 供数据库与业务逻辑统一调用。
"""

from typing import List, Dict, Any

import uuid
from enum import Enum
from tortoise.models import Model
from tortoise import fields


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(Model):
    """聊天消息表，存储所有消息（单用户模式）"""

    message_id = fields.UUIDField(pk=True, default=uuid.uuid4, index=True)
    role = fields.CharField(max_length=20, description="消息角色")
    content = fields.TextField(description="消息内容")
    components = fields.JSONField(default=list, description="消息组件JSON")
    model = fields.CharField(max_length=100, null=True, description="模型名称")
    timestamp = fields.BigIntField(description="消息时间戳")

    class Meta:
        table = "chat_message"
        app = "models"
        # 按时间戳排序，最新的消息在前面
        ordering = ["-timestamp"]

    @property
    def message_components(self) -> List[Dict[str, Any]]:
        """获取消息组件列表"""
        if not self.components:
            # 如果没有组件，尝试将content作为文本组件
            return [{"type": "text", "content": self.content, "extra": None}]
        return self.components

    def get_display_content(self) -> str:
        """获取可显示的消息内容"""
        if not self.components:
            return self.content

        text_parts = []
        for comp in self.components:
            if comp["type"] == "text":
                text_parts.append(comp["content"])
            elif comp["type"] == "audio":
                text_parts.append(f"[音频: {comp['content']}]")
            elif comp["type"] == "image":
                text_parts.append(f"[图片: {comp['content']}]")
            elif comp["type"] == "file":
                text_parts.append(f"[文件: {comp['content']}]")
            elif comp["type"] == "video":
                text_parts.append(f"[视频: {comp['content']}]")
            else:
                text_parts.append(f"[{comp['type']}: {comp['content']}]")

        return " ".join(text_parts)

    def has_component_type(self, component_type: str) -> bool:
        """检查消息是否包含特定类型的组件"""
        return any(comp["type"] == component_type for comp in self.message_components)

    def get_components_by_type(self, component_type: str) -> List[Dict[str, Any]]:
        """获取特定类型的所有组件"""
        return [comp for comp in self.message_components if comp["type"] == component_type]

    @classmethod
    async def from_llm_message(cls, llm_message):
        """从LLMMessage创建ChatMessage"""
        return await cls.create(
            message_id=uuid.UUID(llm_message.message_id),
            role=llm_message.sender.role,
            content=llm_message.message_str,
            components=[
                {"type": comp.type, "content": comp.content, "extra": comp.extra} for comp in llm_message.components
            ],
            timestamp=llm_message.timestamp,
        )
