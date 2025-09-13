"""
app/core/pipeline/function_process.py
函数调用处理流水线。
- 负责函数型消息的处理与分发。
- 支持与历史、LLM等模块协作。
"""

from typing import Optional, Dict, Any, Union

import json
import traceback

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from app import app_config
from app.core.pipeline.text_process import text_process

# from app.core.pipeline.voice_process import voice_process
from app.core.db.db_history import db_message_history
from app.core.llm.message import Message, MessageRole, MessageComponent, MessageSender, MessageType

DEFAULT_MODEL = app_config["llm"]["default_model"]


class FunctionProcess:
    """
    函数调用处理流水线，处理函数调用和结果
    """

    def __init__(self):
        pass

    async def handle_function_result(
        self,
        model: Optional[str],
        function_name: str,
        result: Dict[str, Any],
        history_id: Optional[str],
        stream: bool,
        tts: bool,
        user_id: Optional[str],
        function_message: Message,
    ) -> Union[StreamingResponse, Dict[str, Any]]:
        """
        处理函数调用结果，将结果传递给LLM进行解释和下一步处理

        Args:
            model: 语言模型名称
            function_name: 调用的函数名称
            result: 函数执行结果
            history_id: 历史记录ID
            stream: 是否流式输出
            tts: 是否需要语音合成
            user_id: 用户ID
            function_message: 函数调用结果的消息对象

        Returns:
            LLM对函数结果的解释响应
        """
        try:
            # 确保参数合法
            model = model or DEFAULT_MODEL
            history_id = history_id if history_id and history_id.strip() else None

            # 构建提示词，要求LLM解释函数调用结果
            prompt = f"""用户触发了函数调用: {function_name}
函数执行结果: {json.dumps(result, ensure_ascii=False)}
请以友好的方式向用户解释这个结果。如果结果包含错误，请向用户说明可能的原因。
保持简洁和信息量。
"""

            # 创建系统消息来提示LLM解释函数结果
            system_message = Message(
                history_id=history_id or "",
                sender=MessageSender(role=MessageRole.SYSTEM),
                components=[MessageComponent(type=MessageType.TEXT, content=prompt)],
                message_str=prompt,
            )

            # 如果有历史记录ID，保存系统消息
            if history_id:
                await db_message_history.add_message(history_id, system_message)

            # 根据是否需要流式处理选择不同的处理方法
            if stream:
                return await self._handle_function_stream_response(
                    model, system_message, history_id, user_id, tts, function_name, result
                )
            else:
                return await self._handle_function_normal_response(
                    model, system_message, history_id, user_id, tts, function_name, result
                )

        except HTTPException:
            raise
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"处理函数结果异常: {str(e)}\n{error_trace}")
            raise HTTPException(status_code=500, detail=f"处理函数结果失败: {str(e)}")

    async def _handle_function_stream_response(
        self,
        model: str,
        system_message: Message,
        history_id: Optional[str],
        user_id: Optional[str],
        tts: bool,
        function_name: str,
        result: Dict[str, Any],
    ) -> StreamingResponse:
        """处理函数调用结果的流式响应"""

        async def generate():
            temp_dir = None
            try:
                count = 0
                full_response_text = ""  # 收集完整响应用于TTS
                token_info = None  # 保存token信息
                message_id = None  # 保存原始消息ID
                current_history_id = history_id  # 使用有效的历史ID

                # 添加函数调用结果信息
                function_result_json = json.dumps(result, ensure_ascii=False)
                yield f"data: {json.dumps({'function_call': {'name': function_name, 'result': result}})}\n\n"

                # 处理消息流
                async for chunk in text_process.process_message_stream(
                    model, system_message, current_history_id, user_id
                ):
                    count += 1

                    # 检查是否是token信息特殊标记
                    if chunk.startswith("__TOKEN_INFO__"):
                        try:
                            token_data = json.loads(chunk[14:])  # 去掉特殊前缀
                            token_info = token_data
                            message_id = token_data.get("message_id")
                            if "history_id" in token_data and token_data["history_id"]:
                                current_history_id = token_data["history_id"]
                            token_response = f"data: {json.dumps({'token_info': token_data})}\n\n"
                            yield token_response
                        except Exception as e:
                            logger.error(f"处理token信息失败: {str(e)}")
                    else:
                        # 收集完整响应文本用于TTS
                        full_response_text += chunk
                        # 将普通文本块包装为SSE格式
                        response_text = f"data: {json.dumps({'text': chunk})}\n\n"
                        yield response_text

                # 如果没有生成任何内容
                if count == 0:
                    yield f"data: {json.dumps({'text': '未能生成响应'})}\n\n"

            except Exception as e:
                error_trace = traceback.format_exc()
                logger.error(f"函数结果流式处理失败: {str(e)}\n{error_trace}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                # 标记流结束
                yield "data: [DONE]\n\n"
                # 清理临时文件

        # 确保设置正确的 SSE 响应头
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream",
            },
        )

    async def _handle_function_normal_response(
        self,
        model: str,
        system_message: Message,
        history_id: Optional[str],
        user_id: Optional[str],
        tts: bool,
        function_name: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理函数调用结果的普通响应"""
        try:
            # 处理消息并获取响应
            response = await text_process.process_message(model, system_message, history_id, user_id)

            # 添加函数调用相关信息
            response_dict = response.dict()
            response_dict["function_call"] = {"name": function_name, "result": result}

            return response_dict

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"处理函数结果消息失败: {str(e)}\n{error_trace}")
            raise

    def create_function_stream_response(self, function_name: str, result: Dict[str, Any]) -> StreamingResponse:
        """
        创建函数调用结果的流式响应，不经过LLM处理

        Args:
            function_name: 函数名称
            result: 函数执行结果

        Returns:
            包含函数调用结果的StreamingResponse
        """

        async def generate():
            try:
                # 发送函数调用信息
                yield f"data: {json.dumps({'function_call': {'name': function_name, 'result': result}})}\n\n"

                # 转换函数调用结果为文本
                result_text = json.dumps(result, ensure_ascii=False, indent=2)
                yield f"data: {json.dumps({'text': result_text})}\n\n"

            except Exception as e:
                error_trace = traceback.format_exc()
                logger.error(f"创建函数调用流式响应失败: {str(e)}\n{error_trace}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                # 标记流结束
                yield "data: [DONE]\n\n"

        # 设置SSE响应头
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream",
            },
        )


# 全局函数处理流水线实例
function_process = FunctionProcess()
