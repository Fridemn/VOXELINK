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
    history_id: Optional[str] = None  # 历史ID（单用户模式下可选）
    sender: MessageSender
    components: List[MessageComponent]
    message_str: str
    timestamp: int = Field(default_factory=lambda: int(time.time()))
    raw_message: Optional[Any] = None

    @classmethod
    def from_text(cls, text: str, history_id: Optional[str] = None, role: MessageRole = MessageRole.USER):
        return cls(
            history_id=history_id,
            sender=MessageSender(role=role),
            components=[MessageComponent.create_text(text)],
            message_str=text,
        )

    @classmethod
    def from_audio(
        cls,
        audio_url: str,
        history_id: Optional[str] = None,
        role: MessageRole = MessageRole.USER,
        duration: Optional[float] = None,
        format: Optional[str] = None,
    ):
        component = MessageComponent.create_audio(audio_url, duration, format)
        return cls(
            history_id=history_id,
            sender=MessageSender(role=role),
            components=[component],
            message_str=component.to_display_text(),
        )

    @classmethod
    def from_components(cls, components: List[MessageComponent], history_id: Optional[str] = None, role: MessageRole = MessageRole.USER):
        """从多个组件创建混合类型消息"""
        message_str = " ".join(comp.to_display_text() for comp in components)
        return cls(
            history_id=history_id, sender=MessageSender(role=role), components=components, message_str=message_str
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
