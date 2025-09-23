"""
app/core/db/db_history.py
数据库消息历史管理。
- 提供基于数据库的消息历史存储、查询、管理等功能。
- 支持异步操作。
"""

from typing import List, Optional, Dict, Any
import uuid
import traceback
import os
from fastapi import HTTPException
from tortoise.exceptions import OperationalError, ConfigurationError
from loguru import logger

from ...models.chat import ChatMessage
from ..llm.message import Message, MessageComponent, MessageType
from ... import app_config


class DBMessageHistory:
    def __init__(self):
        self.context_window = getattr(app_config.llm, 'context_window', 10)
        logger.info(f"历史记录上下文窗口大小: {self.context_window}")

    async def _ensure_connection(self):
        try:
            await ChatMessage.all().limit(1)
            return True
        except ConfigurationError:
            return False
        except Exception as e:
            return False

    async def _cleanup_old_messages(self):
        try:
            all_messages = await ChatMessage.all().order_by("-timestamp")
            if len(all_messages) > self.context_window:
                messages_to_delete = all_messages[self.context_window:]
                for msg in messages_to_delete:
                    await msg.delete()
                logger.info(f"清理了 {len(messages_to_delete)} 条超出上下文窗口的旧消息")
        except Exception as e:
            logger.error(f"清理旧消息失败: {e}")

    async def add_message(self, message: Message) -> bool:
        await self._ensure_connection()
        try:
            components = self._process_message_components(message)
            role_value = message.sender.role
            if isinstance(role_value, str) and role_value.startswith("MessageRole."):
                role_value = role_value.split(".")[-1].lower()
            elif hasattr(role_value, "value"):
                role_value = role_value.value

            await ChatMessage.create(
                message_id=uuid.UUID(message.message_id) if message.message_id else uuid.uuid4(),
                role=str(role_value),
                content=message.message_str,
                components=components,
                model=getattr(message.sender, 'nickname', None),
                timestamp=message.timestamp,
            )
            await self._cleanup_old_messages()
            return True
        except OperationalError as e:
            logger.error(f"数据库操作错误: {e}")
            return False
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            traceback.print_exc()
            return False

    def _process_message_components(self, message: Message) -> List[Dict[str, Any]]:
        components = []
        if not message.components:
            return [{"type": "text", "content": message.message_str, "extra": None}]

        for comp in message.components:
            if hasattr(comp, "dict"):
                comp_dict = comp.dict()
                if comp.type == MessageType.AUDIO:
                    if comp.content and comp.content.startswith("/static/audio/"):
                        pass
                    elif comp.extra and "file_path" in comp.extra:
                        file_path = comp.extra["file_path"]
                        if file_path and os.path.exists(file_path):
                            pass
                components.append(comp_dict)
            else:
                components.append(comp)
        return components

    def _convert_db_component_to_message_component(self, comp_data: Dict[str, Any]) -> MessageComponent:
        comp_type = comp_data.get("type", MessageType.TEXT)
        content = comp_data.get("content", "")
        extra = comp_data.get("extra", {})

        if comp_type == MessageType.AUDIO and content:
            file_path = extra.get("file_path", "")
            if file_path and os.path.exists(file_path):
                try:
                    file_size = os.path.getsize(file_path)
                    extra["file_size"] = file_size
                except OSError:
                    pass
            elif content.startswith("/static/audio/"):
                pass
            else:
                extra["available"] = False

        return MessageComponent(type=comp_type, content=content, extra=extra)

    async def get_history(self) -> List[Message]:
        await self._ensure_connection()
        try:
            messages = await ChatMessage.all().order_by("timestamp").limit(self.context_window)
            result = []
            for msg in messages:
                components_data = msg.message_components
                components = []
                for comp_data in components_data:
                    component = self._convert_db_component_to_message_component(comp_data)
                    components.append(component)

                message = Message(
                    message_id=str(msg.message_id),
                    sender={"role": msg.role, "nickname": msg.model},
                    components=components,
                    message_str=msg.content,
                    timestamp=msg.timestamp,
                )
                result.append(message)
            return result
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"获取历史记录失败: {str(e)}\n{error_trace}")
            return []

    async def clear_history(self) -> bool:
        await self._ensure_connection()
        try:
            await ChatMessage.all().delete()
            logger.info("已清空所有历史记录")
            return True
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"清空历史记录失败: {e}\n{error_trace}")
            return False

    async def get_message_count(self) -> int:
        try:
            return await ChatMessage.all().count()
        except Exception as e:
            logger.error(f"获取消息数量失败: {e}")
            return 0

    async def has_audio_message(self) -> bool:
        try:
            messages = await ChatMessage.all()
            for message in messages:
                if message.has_component_type("audio"):
                    return True
            return False
        except Exception as e:
            logger.error(f"检查音频消息失败: {e}")
            return False

    async def delete_message(self, message_id: str) -> bool:
        await self._ensure_connection()
        try:
            try:
                message_uuid = uuid.UUID(message_id)
            except ValueError:
                logger.error(f"无效的消息ID格式: {message_id}")
                return False

            deleted_count = await ChatMessage.filter(message_id=message_uuid).delete()
            if deleted_count > 0:
                logger.info(f"已删除消息: {message_id}")
                return True
            else:
                logger.warning(f"消息不存在: {message_id}")
                return False
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"删除消息失败: {e}\n{error_trace}")
            return False


db_message_history = DBMessageHistory()
