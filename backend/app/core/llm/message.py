"""
app/core/llm/message.py
消息类的统一定义。
- 定义消息类型、角色、消息结构等。
- 供对话、流程等模块统一调用。
"""

from typing import Any, List, Optional

import time
import uuid
from enum import Enum
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageSender(BaseModel):
    role: MessageRole
    nickname: Optional[str] = None


class MessageComponent(BaseModel):
    type: str = "text"
    content: str
    extra: Optional[dict] = None

    @classmethod
    def create_text(cls, text: str) -> "MessageComponent":
        """创建文本类型组件"""
        return cls(type="text", content=text)

    def to_display_text(self) -> str:
        """返回组件的可显示文本"""
        return self.content


class Message(BaseModel):
    """统一的消息格式"""

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: MessageSender
    components: List[MessageComponent]
    message_str: str
    timestamp: int = Field(default_factory=lambda: int(time.time()))
    raw_message: Optional[Any] = None

    @classmethod
    def from_text(cls, text: str, role: MessageRole = MessageRole.USER):
        return cls(
            sender=MessageSender(role=role),
            components=[MessageComponent.create_text(text)],
            message_str=text,
        )

    @classmethod
    def from_audio(
        cls,
        audio_url: str,
        role: MessageRole = MessageRole.USER,
        duration: Optional[float] = None,
        format: Optional[str] = None,
    ):
        extra = {}
        if duration is not None:
            extra["duration"] = duration
        if format is not None:
            extra["format"] = format
            
        component = MessageComponent(type="audio", content=audio_url, extra=extra)
        return cls(
            sender=MessageSender(role=role),
            components=[component],
            message_str=f"[音频: {audio_url}]",
        )

    @classmethod
    def from_components(cls, components: List[MessageComponent], role: MessageRole = MessageRole.USER):
        """从多个组件创建混合类型消息"""
        message_str = " ".join(comp.to_display_text() for comp in components)
        return cls(
            sender=MessageSender(role=role), components=components, message_str=message_str
        )

    def add_component(self, component: MessageComponent) -> "Message":
        """添加新的组件到现有消息"""
        self.components.append(component)
        self.message_str = " ".join(comp.to_display_text() for comp in self.components)
        return self


class Response(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    response_message: Message
    raw_response: Optional[dict] = None
