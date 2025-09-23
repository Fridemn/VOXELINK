"""
app/core/db/db_history.py
数据库消息历史管理。
- 提供基于数据库的消息历史存储、查询、管理等功能。
- 支持异步操作。
"""

from typing import List, Optional, Dict, Any

import os
import time
import uuid
import traceback
from fastapi import HTTPException
from tortoise.exceptions import OperationalError, ConfigurationError
from loguru import logger

from ...models.chat import ChatHistory, ChatMessage, MessageRole
from ..llm.message import Message, MessageComponent, MessageType


class DBMessageHistory:
    """基于数据库的消息历史记录管理"""

    async def _ensure_connection(self):
        """确保数据库连接已初始化"""
        try:
            # 尝试一个简单的查询来测试连接
            await ChatHistory.all().limit(1)
            return True
        except ConfigurationError:
            return False
        except Exception as e:
            return False

    async def get_user_history_id(self, user_id: str) -> str:
        """获取用户的历史记录ID，如果不存在则创建"""
        # 检查连接
        if not await self._ensure_connection():
            raise HTTPException(status_code=500, detail="数据库连接未初始化")

        try:
            # 简化逻辑：直接获取或创建默认的历史记录
            history = await ChatHistory.first()

            # 如果不存在，创建一个新的
            if not history:
                return await self.create_history(user_id)

            return str(history.history_id)
        except Exception as e:
            logger.error(f"获取用户历史记录失败: {e}")
            # 出现异常时创建新历史记录
            return await self.create_history(user_id)

    async def create_history(self, user_id: Optional[str] = None) -> str:
        """创建新的历史记录，一个用户只有一个历史记录"""
        # 检查连接
        if not await self._ensure_connection():
            raise HTTPException(status_code=500, detail="数据库连接未初始化")

        try:
            # 检查是否已有历史记录
            existing_history = await ChatHistory.first()
            if existing_history:
                return str(existing_history.history_id)

            # 创建新的历史记录
            history = await ChatHistory.create()
            return str(history.history_id)
        except Exception as e:
            logger.error(f"创建历史记录失败: {e}")
            return str(uuid.uuid4())

    def _process_message_components(self, message: Message) -> List[Dict[str, Any]]:
        """处理消息组件，确保正确格式化并处理特殊类型"""
        components = []

        if not message.components:
            # 如果没有组件，使用message_str作为默认文本组件
            return [{"type": "text", "content": message.message_str, "extra": None}]

        for comp in message.components:
            if hasattr(comp, "dict"):
                comp_dict = comp.dict()

                # 特殊处理音频类型
                if comp.type == MessageType.AUDIO:
                    # 确保保留音频文件路径和转录文本
                    if not comp_dict.get("extra"):
                        comp_dict["extra"] = {}

                components.append(comp_dict)
            else:
                # 兼容直接传入dict的情况
                components.append(comp)

        return components

    async def add_message(self, history_id: str, message: Message) -> bool:
        """添加消息到历史记录"""
        # 确保连接已初始化
        await self._ensure_connection()

        try:
            # 验证history_id
            if not history_id or not history_id.strip():
                logger.error("无效的历史记录ID")
                return False

            # 确保history_id存在
            try:
                history_uuid = uuid.UUID(history_id)
                history = await ChatHistory.filter(history_id=history_uuid).first()
                if not history:
                    # 如果历史记录不存在，则创建一个
                    history = await ChatHistory.create(history_id=history_uuid)

                # 处理消息组件，确保正确格式化
                components = self._process_message_components(message)

                # 处理角色值，确保只存储实际角色值（如"user"、"assistant"、"system"）
                role_value = message.sender.role
                # 如果角色是字符串形式的枚举（如"MessageRole.ASSISTANT"），提取实际值
                if isinstance(role_value, str) and role_value.startswith("MessageRole."):
                    role_value = role_value.split(".", 1)[1].lower()
                # 如果角色是枚举对象，获取其值
                elif hasattr(role_value, "value"):
                    role_value = role_value.value

                # 准备消息数据
                message_data = {
                    "message_id": uuid.UUID(message.message_id) if message.message_id else uuid.uuid4(),
                    "history": history,
                    "role": role_value,
                    "content": message.message_str,
                    "components": components,
                    "model": message.sender.nickname,
                    # 用户消息使用传入的时间戳，AI消息使用当前时间戳
                    "timestamp": (
                        message.timestamp
                        if role_value in [MessageRole.USER, MessageRole.SYSTEM] and message.timestamp
                        else int(time.time())
                    ),
                }

                # 创建新消息记录
                await ChatMessage.create(**message_data)

                # 更新历史记录的更新时间
                history.update_time = time.time()
                await history.save()

                return True
            except ValueError as e:
                logger.error(f"无效的UUID格式: {e}")
                return False

        except OperationalError as e:
            logger.error(f"数据库操作错误: {e}")
            return False
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            traceback.print_exc()
            return False

    def _convert_db_component_to_message_component(self, comp_data: Dict[str, Any]) -> MessageComponent:
        """将数据库中的组件数据转换为MessageComponent对象"""
        comp_type = comp_data.get("type", MessageType.TEXT)
        content = comp_data.get("content", "")
        extra = comp_data.get("extra", {})

        # 特殊处理音频类型
        if comp_type == MessageType.AUDIO and content:
            # 检查原始文件路径是否存在于extra中
            file_path = extra.get("file_path", "")

            # 如果有原始文件路径且文件存在，更新元数据
            if file_path and os.path.exists(file_path):
                if not extra:
                    extra = {}
                extra["file_exists"] = True
                # 添加文件大小信息
                try:
                    extra["file_size"] = os.path.getsize(file_path)
                except:
                    pass
            elif content.startswith("/static/audio/"):
                # 尝试从URL路径构造本地路径进行检查
                try:
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                    potential_path = os.path.join(base_dir, content[1:])  # 去掉开头的"/"
                    if os.path.exists(potential_path):
                        if not extra:
                            extra = {}
                        extra["file_exists"] = True
                        extra["file_size"] = os.path.getsize(potential_path)
                        # 更新文件路径用于未来检查
                        extra["file_path"] = potential_path
                    else:
                        if not extra:
                            extra = {}
                        extra["file_exists"] = False
                except:
                    if not extra:
                        extra = {}
                    extra["file_exists"] = False
            else:
                # 文件不存在，标记状态
                if not extra:
                    extra = {}
                extra["file_exists"] = False
                logger.warning(f"从数据库加载时，音频文件不存在: {content}")

        return MessageComponent(type=comp_type, content=content, extra=extra)

    async def get_history(self, history_id: str) -> List[Message]:
        """获取历史记录中的消息"""
        # 确保连接已初始化
        await self._ensure_connection()

        try:
            # 验证history_id格式
            try:
                history_uuid = uuid.UUID(history_id)
            except ValueError:
                logger.error(f"无效的历史记录ID格式: {history_id}")
                return []

            # 检查历史记录是否存在
            history = await ChatHistory.filter(history_id=history_uuid).first()
            if not history:
                logger.warning(f"历史记录不存在: {history_id}")
                return []

            # 获取该历史记录的所有消息
            messages = await ChatMessage.filter(history_id=history_uuid).order_by("timestamp").all()

            result = []
            for msg in messages:
                try:
                    # 解析组件数据
                    components_data = msg.message_components

                    # 构造组件对象
                    components = []
                    for comp_data in components_data:
                        if not isinstance(comp_data, dict):
                            continue

                        components.append(self._convert_db_component_to_message_component(comp_data))

                    role = msg.role
                    if role.startswith("MessageRole."):
                        actual_role = role.split(".", 1)[1].lower()
                        if actual_role in ["user", "assistant", "system"]:
                            role = actual_role
                        else:
                            role = "user"

                    # 创建消息对象
                    message = Message(
                        message_id=str(msg.message_id),
                        history_id=history_id,
                        sender={"role": role, "nickname": msg.model},
                        components=components,
                        message_str=msg.content,
                        timestamp=msg.timestamp,
                    )
                    result.append(message)
                except Exception as e:
                    error_trace = traceback.format_exc()
                    logger.error(f"处理消息时出错: {str(e)}\n{error_trace}")

            return result
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"获取历史记录失败: {str(e)}\n{error_trace}")
            return []

    async def delete_history(self, history_id: str) -> bool:
        """删除历史记录，但保留用户关联，只清空消息"""
        await self._ensure_connection()

        try:
            # 验证history_id格式
            try:
                history_uuid = uuid.UUID(history_id)
            except ValueError:
                logger.error(f"无效的历史记录ID格式: {history_id}")
                return False

            # 首先删除关联的消息
            await ChatMessage.filter(history_id=history_uuid).delete()

            # 不删除历史记录，而是清空消息后保留
            history = await ChatHistory.filter(history_id=history_uuid).first()
            if history:
                history.update_time = time.time()
                await history.save()
                return True
            else:
                logger.warning(f"历史记录不存在: {history_id}")
                return False

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"清空历史记录失败: {e}\n{error_trace}")
            return False

    async def completely_delete_history(self, history_id: str) -> bool:
        """完全删除历史记录，包括历史记录本身（用于清理临时记录）"""
        await self._ensure_connection()

        try:
            # 验证history_id格式
            try:
                history_uuid = uuid.UUID(history_id)
            except ValueError:
                logger.error(f"无效的历史记录ID格式: {history_id}")
                return False

            # 首先删除关联的消息
            await ChatMessage.filter(history_id=history_uuid).delete()

            # 然后删除历史记录本身
            deleted_count = await ChatHistory.filter(history_id=history_uuid).delete()

            if deleted_count > 0:
                logger.info(f"完全删除历史记录: {history_id}")
                return True
            else:
                logger.warning(f"要删除的历史记录不存在: {history_id}")
                return False

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"删除历史记录失败: {e}\n{error_trace}")
            return False

    async def get_user_history(self, user_id: str) -> Optional[dict]:
        """获取用户的聊天历史，每个用户只有一条历史记录"""
        # 确保连接已初始化
        await self._ensure_connection()

        try:
            # 获取用户的历史记录（由于模型设计，每个用户只有一条历史记录）
            history = await ChatHistory.first()

            if not history:
                # 如果不存在，创建一个新的
                history_id = await self.create_history(user_id)
                history = await ChatHistory.filter(history_id=history_id).first()
                if not history:
                    return None

            # 获取历史记录的消息数量
            message_count = await ChatMessage.filter(history_id=history.history_id).count()

            return {
                "history_id": str(history.history_id),
                "create_time": history.create_time.isoformat(),
                "update_time": history.update_time.isoformat(),
                "message_count": message_count,
            }
        except Exception as e:
            logger.error(f"获取用户历史记录失败: {e}")
            return None

    async def update_message(self, history_id: str, message_id: str, updates: dict) -> bool:
        """更新历史记录中的特定消息"""
        try:
            # 直接更新消息表中的记录
            message = await ChatMessage.filter(
                history_id=uuid.UUID(history_id), message_id=uuid.UUID(message_id)
            ).first()

            if not message:
                return False

            # 更新消息字段
            for key, value in updates.items():
                setattr(message, key, value)

            await message.save()
            return True
        except Exception as e:
            logger.error(f"更新消息失败: {e}")
            return False

    async def get_message_by_id(self, history_id: str, message_id: str) -> Optional[Message]:
        """根据ID获取特定消息"""
        try:
            message = await ChatMessage.filter(
                history_id=uuid.UUID(history_id), message_id=uuid.UUID(message_id)
            ).first()

            if not message:
                return None

            # 转换为LLMMessage格式
            components_data = message.message_components
            components = []

            for comp_data in components_data:
                if not isinstance(comp_data, dict):
                    continue
                components.append(self._convert_db_component_to_message_component(comp_data))

            return Message(
                message_id=str(message.message_id),
                history_id=str(message.history_id),
                sender={"role": message.role, "nickname": message.model},
                components=components,
                message_str=message.content,
                timestamp=message.timestamp,
            )

        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            return None

    async def has_audio_message(self, history_id: str) -> bool:
        """检查历史记录中是否包含音频消息"""
        try:
            messages = await ChatMessage.filter(history_id=uuid.UUID(history_id)).all()

            for message in messages:
                components = message.message_components
                for comp in components:
                    if isinstance(comp, dict) and comp.get("type") == MessageType.AUDIO:
                        return True

            return False
        except Exception as e:
            logger.error(f"检查音频消息失败: {e}")
            return False

    async def delete_message(self, history_id: str, message_id: str) -> bool:
        """删除历史记录中的特定消息"""
        # 确保连接已初始化
        await self._ensure_connection()

        try:
            # 验证ID格式
            try:
                history_uuid = uuid.UUID(history_id)
                message_uuid = uuid.UUID(message_id)
            except ValueError:
                logger.error(f"无效的ID格式: history_id={history_id}, message_id={message_id}")
                return False

            # 删除消息
            deleted_count = await ChatMessage.filter(history_id=history_uuid, message_id=message_uuid).delete()

            if deleted_count > 0:
                return True
            else:
                logger.warning(f"要删除的消息不存在: history_id={history_id}, message_id={message_id}")
                return False

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"删除消息失败: {e}\n{error_trace}")
            return False


# 创建全局实例
db_message_history = DBMessageHistory()
