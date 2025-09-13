"""
app/core/pipeline/chat_process.py
聊天处理流水线。
- 负责整合文本和语音的聊天处理流程。
- 支持多模型、多轮对话。
"""

from typing import Optional, Dict, Any, Union

import json
import traceback

from fastapi import UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from app import app_config
from app.core.pipeline.text_process import text_process
from app.core.llm.message import Message, Response, MessageRole
from app.core.tts.tts_service import text_to_speech_stream
import asyncio
import re


def _get_default_model():
    """安全获取默认LLM模型"""
    try:
        return app_config["llm"]["default_model"]
    except Exception:
        # 回退到硬编码的默认值
        return "gpt-3.5-turbo"


DEFAULT_MODEL = _get_default_model()


class ChatProcess:
    """
    聊天处理流水线，整合文本和语音处理流程
    """

    def __init__(self):
        pass

    async def handle_request(
        self,
        model: Optional[str],
        message: Optional[str],
        history_id: Optional[str],
        role: MessageRole,
        stream: bool,
        stt: bool,
        tts: bool,
        audio_file: Optional[UploadFile],
        user_id: Optional[str],
    ) -> Union[StreamingResponse, Response, Dict[str, Any]]:
        """
        处理统一聊天请求

        Args:
            model: LLM模型名称
            message: 文本消息
            history_id: 对话历史ID
            role: 消息角色
            stream: 是否流式响应
            stt: 是否需要语音转文本
            tts: 是否需要文本转语音
            audio_file: 上传的音频文件
            user_id: 用户ID
            user_token: 用户认证token，用于TTS服务

        Returns:
            StreamingResponse或Response
        """
        # 初始化变量
        input_message = None
        transcribed_text = None

        try:
            # 确保参数合法
            model = model or DEFAULT_MODEL
            history_id = history_id if history_id and history_id.strip() else None

            # 准备输入消息
            input_message = await self._prepare_input_message(
                message,
                history_id,
                role,
                stt,
                audio_file,
            )

            # 如果是语音输入，获取语音转写文本
            if stt and audio_file and hasattr(input_message, "message_str"):
                transcribed_text = input_message.message_str

            # 根据流式处理需求选择处理方式
            if stream:
                return await self._handle_stream_response(
                    model, input_message, history_id, user_id, stt, tts, transcribed_text
                )
            else:
                return await self._handle_normal_response(model, input_message, history_id, user_id, tts)

        except HTTPException:
            raise
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"聊天处理流水线异常: {str(e)}\n{error_trace}")
            raise HTTPException(status_code=500, detail=f"处理请求失败: {str(e)}")

    async def _prepare_input_message(
        self,
        message: Optional[str],
        history_id: Optional[str],
        role: MessageRole,
        stt: bool = False,
        audio_file: Optional[UploadFile] = None,
    ) -> Message:
        """
        根据请求参数准备输入消息

        Args:
            message: 文本消息
            history_id: 对话历史ID
            role: 消息角色
            stt: 是否需要语音转文本
            audio_file: 上传的音频文件

        Returns:
            Message消息对象
        """

        try:
            # 如果有音频文件且需要STT处理
            if stt and audio_file:
                # TODO: 这里应该集成STT服务来处理音频文件
                # 暂时抛出错误，因为STT功能还未实现
                raise HTTPException(status_code=501, detail="语音转文本功能暂未实现")

            # 处理纯文本输入
            if not message or not message.strip():
                raise HTTPException(status_code=400, detail="消息内容不能为空")

            # 构造输入消息
            return Message.from_text(text=message, history_id=history_id or "", role=role)

        except Exception as e:
            logger.error(f"准备输入消息失败: {str(e)}")
            raise

    async def _handle_stream_response(
        self,
        model: str,
        input_message: Message,
        history_id: Optional[str],
        user_id: Optional[str],
        stt: bool,
        tts: bool,
        transcribed_text: Optional[str],
    ) -> StreamingResponse:
        """
        处理流式响应

        Returns:
            StreamingResponse对象
        """

        async def generate():
            text_buffer = ""  # 用于拼接文本块
            sentence_delimiters = re.compile(r"([。！？，])")  # 定义句子分隔符

            async def process_tts_queue(queue):
                while True:
                    text_chunk = await queue.get()
                    if text_chunk is None:
                        logger.info("TTS处理任务收到停止信号，正常退出。")
                        break
                    logger.info(f"发送文本块到TTS服务: '{text_chunk}'")
                    await text_to_speech_stream(text_chunk)
                    queue.task_done()

            tts_queue = asyncio.Queue()
            tts_task = None
            if tts:
                logger.info("创建TTS处理任务。")
                tts_task = asyncio.create_task(process_tts_queue(tts_queue))

            try:
                count = 0
                full_response_text = ""  # 收集完整响应用于TTS
                token_info = None  # 保存token信息
                message_id = None  # 保存原始消息ID
                current_history_id = history_id or input_message.history_id  # 使用有效的历史ID

                # 如果是语音输入，先返回识别结果
                if stt and transcribed_text:
                    yield f"data: {json.dumps({'transcription': transcribed_text})}\n\n"

                # 处理消息流
                async for chunk in text_process.process_message_stream(
                    model, input_message, current_history_id, user_id  # 使用确定的历史ID
                ):
                    count += 1

                    # 检查是否是token信息特殊标记
                    if chunk.startswith("__TOKEN_INFO__"):
                        try:
                            token_data = json.loads(chunk[14:])  # 去掉特殊前缀
                            token_info = token_data
                            message_id = token_data.get("message_id")
                            # 如果token信息中包含了history_id，使用它更新当前历史ID
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
                        if tts:
                            text_buffer += chunk
                            parts = sentence_delimiters.split(text_buffer)
                            
                            # 处理切分后的部分
                            for i in range(len(parts) // 2):
                                sentence = parts[2*i] + parts[2*i+1]
                                if sentence.strip():
                                    logger.debug(f"将句子放入TTS队列: '{sentence.strip()}'")
                                    await tts_queue.put(sentence.strip())
                            
                            # 更新缓冲区为剩余的未切分部分
                            if len(parts) % 2 == 1:
                                text_buffer = parts[-1]
                            else:
                                text_buffer = ""


                # 如果没有生成任何内容
                if count == 0:
                    yield f"data: {json.dumps({'text': '未能生成响应'})}\n\n"

                # 处理缓冲区中剩余的文本
                if tts and text_buffer.strip():
                    logger.debug(f"将缓冲区剩余文本放入TTS队列: '{text_buffer.strip()}'")
                    await tts_queue.put(text_buffer.strip())

            except Exception as e:
                error_trace = traceback.format_exc()
                logger.error(f"流式处理失败: {str(e)}\n{error_trace}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                if tts_task:
                    logger.info("所有文本块已处理，向TTS任务发送停止信号。")
                    await tts_queue.put(None)  # 发送停止信号
                    await tts_task  # 等待TTS任务完成
                yield "data: [DONE]\n\n"

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

    async def _handle_normal_response(
        self,
        model: str,
        input_message: Message,
        history_id: Optional[str],
        user_id: Optional[str],
        tts: bool = False,
    ) -> Union[Response, Dict[str, Any]]:
        """
        处理普通（非流式）响应

        Args:
            model: LLM模型名称
            input_message: 输入消息
            history_id: 对话历史ID
            user_id: 用户ID
            tts: 是否需要文本转语音

        Returns:
            Response或包含响应信息的字典
        """
        try:
            # 使用文本处理流水线处理消息
            response = await text_process.process_message(model, input_message, history_id, user_id)

            # 如果需要TTS处理
            if tts and response and hasattr(response, "response_text"):
                # TODO: 这里应该集成TTS服务来处理语音合成
                # 暂时返回响应，不进行TTS处理
                logger.info("TTS功能暂未实现，跳过语音合成")

            return response

        except HTTPException:
            raise
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"普通响应处理失败: {str(e)}\n{error_trace}")
            raise


# 全局聊天处理流水线实例
chat_process = ChatProcess()
