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

from ... import app_config
from .text_process import get_text_process
from ..tts.tts_service import text_to_speech_stream
from ..llm.message import Message, Response, MessageRole
import asyncio
import re
import base64
from ...services.asr_service import get_asr_service


from ...services.asr_service import get_asr_service


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
            role: 消息角色
            stream: 是否流式响应
            stt: 是否需要语音转文本
            tts: 是否需要文本转语音
            audio_file: 上传的音频文件
            user_id: 用户ID

        Returns:
            StreamingResponse或Response
        """
        # 初始化变量
        input_message = None
        transcribed_text = None

        try:
            # 确保参数合法
            model = model or DEFAULT_MODEL

            # 准备输入消息
            input_message = await self._prepare_input_message(
                message,
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
                    model, input_message, user_id, stt, tts, transcribed_text
                )
            else:
                return await self._handle_normal_response(model, input_message, user_id, tts)

        except HTTPException:
            raise
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"聊天处理流水线异常: {str(e)}\n{error_trace}")
            raise HTTPException(status_code=500, detail=f"处理请求失败: {str(e)}")

    async def _prepare_input_message(
        self,
        message: Optional[str],
        role: MessageRole,
        stt: bool = False,
        audio_file: Optional[UploadFile] = None,
    ) -> Message:
        """
        根据请求参数准备输入消息

        Args:
            message: 文本消息
            role: 消息角色
            stt: 是否需要语音转文本
            audio_file: 上传的音频文件

        Returns:
            Message消息对象
        """

        try:
            # 如果有音频文件且需要STT处理
            if stt and audio_file:
                # 获取ASR服务实例
                asr_service = get_asr_service()
                
                # 读取音频文件内容
                audio_data = await audio_file.read()
                
                # 根据文件扩展名推断音频格式
                filename = audio_file.filename or ""
                if filename.lower().endswith('.wav'):
                    audio_format = "wav"
                elif filename.lower().endswith('.pcm'):
                    audio_format = "pcm"
                else:
                    audio_format = "auto"  # 让ASR服务自动检测
                
                # 执行语音识别
                recognition_result = asr_service.recognize(audio_data, audio_format=audio_format)
                
                if not recognition_result.get("success", False):
                    error_msg = recognition_result.get("error", "语音识别失败")
                    raise HTTPException(status_code=400, detail=f"语音识别失败: {error_msg}")
                
                # 获取识别的文本
                transcribed_text = recognition_result.get("text", "").strip()
                if not transcribed_text:
                    raise HTTPException(status_code=400, detail="未能识别到有效语音内容")
                
                logger.info(f"语音识别成功: {transcribed_text}")
                
                # 使用识别的文本构造消息
                return Message.from_text(text=transcribed_text, role=role)

            # 处理纯文本输入
            if not message or not message.strip():
                raise HTTPException(status_code=400, detail="消息内容不能为空")

            # 构造输入消息
            return Message.from_text(text=message, role=role)

        except Exception as e:
            logger.error(f"准备输入消息失败: {str(e)}")
            raise

    async def _handle_stream_response(
        self,
        model: str,
        input_message: Message,
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

            async def process_tts_queue(queue, yield_queue):
                while True:
                    text_chunk = await queue.get()
                    if text_chunk is None:
                        logger.info("TTS处理任务收到停止信号，正常退出。")
                        break
                    logger.info(f"发送文本块到TTS服务: '{text_chunk}'")
                    result = await text_to_speech_stream(text_chunk)
                    if result:
                        sr, audio_bytes = result
                        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                        await yield_queue.put(f"data: {json.dumps({'audio': audio_base64})}\n\n")
                    queue.task_done()

            tts_queue = asyncio.Queue()
            yield_queue = asyncio.Queue()
            text_queue = asyncio.Queue()
            tts_task = None
            text_task = None
            if tts:
                logger.info("创建TTS处理任务。")
                tts_task = asyncio.create_task(process_tts_queue(tts_queue, yield_queue))

            async def collect_text():
                async for chunk in get_text_process().process_message_stream(
                    model, input_message, skip_db=False
                ):
                    await text_queue.put(chunk)
                await text_queue.put(None)

            text_task = asyncio.create_task(collect_text())

            try:
                count = 0
                full_response_text = ""  # 收集完整响应用于TTS

                # 如果是语音输入，先返回识别结果
                if stt and transcribed_text:
                    yield f"data: {json.dumps({'transcription': transcribed_text})}\n\n"

                # 处理消息流
                while True:
                    chunk = await text_queue.get()
                    if chunk is None:
                        break
                    count += 1

                    # 收集完整响应文本用于TTS
                    full_response_text += chunk
                    # 将普通文本块包装为SSE格式
                    response_text = f"data: {json.dumps({'text': chunk})}\n\n"
                    yield response_text
                    
                    # 检查是否有音频准备好
                    if tts:
                        try:
                            audio_data = await asyncio.wait_for(yield_queue.get(), timeout=0.01)
                            yield audio_data
                            yield_queue.task_done()
                        except asyncio.TimeoutError:
                            pass
                        
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

                # 等待TTS任务完成并发送剩余音频
                if tts_task:
                    await tts_queue.put(None)
                    await tts_task
                    while not yield_queue.empty():
                        audio_data = await yield_queue.get()
                        yield audio_data
                        yield_queue.task_done()

            except Exception as e:
                error_trace = traceback.format_exc()
                logger.error(f"流式处理失败: {str(e)}\n{error_trace}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                if text_task and not text_task.done():
                    await text_task
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
        user_id: Optional[str],
        tts: bool = False,
    ) -> Union[Response, Dict[str, Any]]:
        """
        处理普通（非流式）响应

        Args:
            model: LLM模型名称
            input_message: 输入消息
            user_id: 用户ID
            tts: 是否需要文本转语音

        Returns:
            Response或包含响应信息的字典
        """
        try:
            # 使用文本处理流水线处理消息
            response = await get_text_process().process_message(model, input_message, skip_db=False)

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
