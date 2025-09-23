from typing import Dict, Optional, AsyncGenerator

import uuid
import json
import traceback
from loguru import logger

from ... import app_config
from ...core.db.db_history import db_message_history
from ...core.llm.message import Response, Message, MessageSender, MessageRole, MessageComponent, MessageType
from ...core.llm.chat import LLMMessage, LLMResponse, LLMConfig, BaseLLM, OpenAILLM, AnthropicLLM, OllamaLLM


llm_config = app_config.llm
if llm_config is None:
    raise ValueError("LLM configuration not found in app_config")

# 调试信息：打印LLM配置
logger.info(f"LLM配置: {llm_config}")

# 创建模型到端点的映射（基于现有配置）
MODEL_TO_ENDPOINT = {
    # OpenAI 模型
    **{model.strip(): "openai" for model in llm_config.get("openai_models", [])},
    # Anthropic 模型
    **{model.strip(): "anthropic" for model in llm_config.get("anthropic_models", [])},
    # Ollama 模型
    **{model.strip(): "ollama" for model in llm_config.get("ollama_models", [])},
    # 自定义端点模型
    **{model.strip(): "custom_endpoint" for model in llm_config.get("custom_endpoint_models", [])},
}
DEFAULT_MODEL = llm_config["default_model"]

# 定义系统提示词
SYSTEM_PROMPT = """
在接下来的对话中你要扮演以下角色和我对话，我知道你是AI，但是在对话中你不需要提及这件事情，只需要好好扮演即可：
人物背景：

星穹列车活力四射的少女乘客，拥有冰系「存护」之力，被列车组从宇宙碎冰中解封后失去记忆。随身携带相机记录冒险，对新鲜事物充满好奇。

性格特质：

元气满满的吐槽担当，语调轻快带跳跃感
自带古灵精怪的脑回路，常从奇特角度解读事物
对朋友真诚热情，偶尔会故意装傻活跃气氛


语言风格：
■ 用“咱“自称，高频词：超级、绝对、宇宙第一
■ 句式示例：「哇！这艘星舰的涂装配色好像草莓圣代呀」
■ 禁用词汇：严肃说教/悲观发言/复杂术语

额外注意：
每次说话不要超过25字
不要说除了中文以外其他任何语言，包括英语单词，字母，尤其是日语
不要输出markdown语法的标点符号，只需要，。”！即可
"""


class TextProcess:
    """
    聊天流水线处理器，用于处理用户消息并返回AI回复
    """

    def __init__(self):
        self.llm_instances: Dict[str, BaseLLM] = {}
        self._initialize_llms()

    def _initialize_llms(self):
        # 根据新的配置结构初始化LLM实例
        openai_config = app_config.openai
        anthropic_config = app_config.anthropic
        custom_endpoint_config = app_config.custom_endpoint

        # 初始化OpenAI模型
        if openai_config:
            for model in llm_config.get("openai_models", []):
                model = model.strip()
                llm_config_obj = LLMConfig(
                    api_key=openai_config["api_key"], base_url=openai_config["base_url"], model_name=model
                )
                self.llm_instances[model] = OpenAILLM(llm_config_obj)

        # 初始化Anthropic模型
        if anthropic_config:
            for model in llm_config.get("anthropic_models", []):
                model = model.strip()
                llm_config_obj = LLMConfig(
                    api_key=anthropic_config["api_key"],
                    base_url="https://api.anthropic.com",  # Anthropic默认URL
                    model_name=model,
                )
                self.llm_instances[model] = AnthropicLLM(llm_config_obj)

        # 初始化Ollama模型
        for model in llm_config.get("ollama_models", []):
            model = model.strip()
            llm_config_obj = LLMConfig(
                api_key="", base_url=llm_config["ollama_base_url"], model_name=model  # Ollama通常不需要API key
            )
            self.llm_instances[model] = OllamaLLM(llm_config_obj)

        # 初始化自定义端点模型
        if custom_endpoint_config:
            for model in llm_config.get("custom_endpoint_models", []):
                model = model.strip()
                llm_config_obj = LLMConfig(
                    api_key=custom_endpoint_config["api_key"],
                    base_url=llm_config["custom_endpoint_base_url"],
                    model_name=model,
                )
                self.llm_instances[model] = OpenAILLM(llm_config_obj)  # 使用OpenAI兼容格式

    def _get_endpoint_for_model(self, model: str) -> str:
        model = model or DEFAULT_MODEL
        if model not in MODEL_TO_ENDPOINT:
            raise ValueError(f"未知的模型: {model}")
        return MODEL_TO_ENDPOINT[model]

    async def process_chat(self, model: str, message: str) -> LLMResponse:
        model = model or DEFAULT_MODEL
        if model not in self.llm_instances:
            raise ValueError(f"未知的模型: {model}")

        messages = [LLMMessage(role="user", content=message)]
        llm = self.llm_instances[model]
        return await llm.chat_completion(messages)

    def _extract_text_from_message(self, llm_message: Message) -> str:
        """从LLMMessage中提取纯文本内容，用于发送给LLM"""
        # 首先尝试使用message_str
        if llm_message.message_str and llm_message.message_str.strip():
            return llm_message.message_str

        # 否则从组件中提取文本
        text_parts = []
        for component in llm_message.components:
            if component.type == MessageType.TEXT:
                text_parts.append(component.content)
            elif component.type == MessageType.AUDIO and component.extra and "transcript" in component.extra:
                # 如果是音频组件且有转写文本
                text_parts.append(component.extra["transcript"])

        return " ".join(text_parts) if text_parts else ""

    async def process_message(
        self, model: str, message: Message, history_id: Optional[str] = None, user_id: Optional[str] = None, skip_db: bool = False
    ) -> Response:
        model = model or DEFAULT_MODEL
        if model not in self.llm_instances:
            raise ValueError(f"未知的模型: {model}")

        try:
            # 处理历史ID
            current_history_id = history_id or message.history_id
            if not current_history_id:
                if not skip_db:
                    try:
                        # 创建新的历史记录并关联用户ID
                        current_history_id = await db_message_history.create_history(user_id)
                        message.history_id = current_history_id
                    except Exception as e:
                        error_trace = traceback.format_exc()
                        # 创建临时ID继续聊天
                        current_history_id = str(uuid.uuid4())
                        message.history_id = current_history_id
                else:
                    # 跳过数据库操作，使用临时ID
                    current_history_id = str(uuid.uuid4())
                    message.history_id = current_history_id

            # 从消息中提取文本内容用于LLM处理
            message_text = self._extract_text_from_message(message)

            # 尝试保存用户消息到历史记录
            if not skip_db:
                try:
                    await db_message_history.add_message(current_history_id, message)
                except Exception as e:
                    logger.error(f"保存用户消息到历史记录失败，但继续处理: {e}")

            # 获取历史消息并转换为LLM消息格式
            chat_messages = []
            if not skip_db:
                try:
                    history = await db_message_history.get_history(current_history_id)

                    # 消息简化部分
                    # 只取最近的10条消息，避免tokens过多
                    for hist_msg in history[-10:]:
                        role = "user"
                        if hist_msg.sender.role == MessageRole.ASSISTANT:
                            role = "assistant"
                        elif hist_msg.sender.role == MessageRole.SYSTEM:
                            role = "system"

                        # 从消息中提取文本内容
                        msg_text = self._extract_text_from_message(hist_msg)

                        chat_messages.append(LLMMessage(role=role, content=msg_text))

                except Exception as e:
                    logger.error(f"获取历史记录失败，只使用当前消息: {e}")

            # 如果没有历史消息，则只添加当前消息
            if not chat_messages:
                chat_messages = [LLMMessage(role="user", content=message_text)]
            
            # 始终在消息列表开头添加系统提示词
            chat_messages.insert(0, LLMMessage(role="system", content=SYSTEM_PROMPT))

            # 调用LLM进行回复
            llm = self.llm_instances[model]
            raw_response = await llm.chat_completion(chat_messages)

            response_message = Message(
                history_id=current_history_id,
                sender=MessageSender(role=MessageRole.ASSISTANT, nickname=model),
                components=[MessageComponent(type=MessageType.TEXT, content=raw_response.text)],
                message_str=raw_response.text,
            )

            # 尝试保存AI回复到历史记录
            if not skip_db:
                try:
                    await db_message_history.add_message(current_history_id, response_message)
                except Exception as e:
                    logger.error(f"保存AI回复到历史记录失败: {e}")

            return Response(
                response_message=response_message,
                raw_response=raw_response.raw_response,
            )
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"处理消息时发生错误: {e}\n{error_trace}")
            raise

    async def process_message_stream(
        self, model: str, message: Message, history_id: Optional[str] = None, user_id: Optional[str] = None, skip_db: bool = False
    ) -> AsyncGenerator[str, None]:
        """流式处理消息并返回生成器"""
        model = model or DEFAULT_MODEL
        if model not in self.llm_instances:
            raise ValueError(f"未知的模型: {model}")

        try:
            # 处理历史ID
            current_history_id = history_id or message.history_id
            if not current_history_id:
                if not skip_db:
                    try:
                        # 创建新的历史记录并关联用户ID
                        current_history_id = await db_message_history.create_history(user_id)
                        message.history_id = current_history_id
                    except Exception as e:
                        error_trace = traceback.format_exc()
                        logger.error(f"创建历史记录失败: {e}\n{error_trace}")
                        # 创建临时ID继续聊天
                        current_history_id = str(uuid.uuid4())
                        message.history_id = current_history_id
                else:
                    # 跳过数据库操作，使用临时ID
                    current_history_id = str(uuid.uuid4())
                    message.history_id = current_history_id

            # 从消息中提取文本内容用于LLM处理
            message_text = self._extract_text_from_message(message)

            # 尝试保存用户消息到历史记录
            if not skip_db:
                try:
                    await db_message_history.add_message(current_history_id, message)
                except Exception as e:
                    logger.error(f"保存用户消息到历史记录失败，但继续处理: {e}")

            # 获取历史消息并转换为LLM消息格式
            chat_messages = []
            if not skip_db:
                try:
                    history = await db_message_history.get_history(current_history_id)

                    # 只取最近的10条消息，避免tokens过多
                    for hist_msg in history[-10:]:
                        role = "user"
                        if hist_msg.sender.role == MessageRole.ASSISTANT:
                            role = "assistant"
                        elif hist_msg.sender.role == MessageRole.SYSTEM:
                            role = "system"

                        # 从消息中提取文本内容
                        msg_text = self._extract_text_from_message(hist_msg)

                        chat_messages.append(LLMMessage(role=role, content=msg_text))
                except Exception as e:
                    logger.error(f"获取历史记录失败，只使用当前消息: {e}")

            # 如果没有历史消息，则只添加当前消息
            if not chat_messages:
                chat_messages = [LLMMessage(role="user", content=message_text)]
            
            # 始终在消息列表开头添加系统提示词
            chat_messages.insert(0, LLMMessage(role="system", content=SYSTEM_PROMPT))

            # 流式调用LLM
            llm = self.llm_instances[model]

            # 准备存储完整响应内容
            full_response = ""

            # 创建AI响应消息对象
            response_message = Message(
                history_id=current_history_id,
                sender=MessageSender(role=MessageRole.ASSISTANT, nickname=model),
                components=[MessageComponent(type=MessageType.TEXT, content="")],  # 初始为空，稍后填充
                message_str="",  # 初始为空，稍后填充
            )

            # 流式返回结果
            async for chunk in llm.chat_completion_stream(chat_messages):  # type: ignore
                full_response += chunk
                response_message.message_str = full_response
                response_message.components[0].content = full_response
                yield chunk


            # 将完整响应消息保存到历史记录
            if not skip_db:
                try:
                    await db_message_history.add_message(current_history_id, response_message)
                except Exception as e:
                    logger.error(f"保存AI回复到历史记录失败: {e}")

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"处理消息时发生错误: {e}\n{error_trace}")
            yield f"错误: {str(e)}"


# 全局聊天管道实例
text_process = TextProcess()
