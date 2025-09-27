"""
WebSocket API路由 - 仅实时语音聊天
"""

import logging
import json
import base64
import asyncio
from typing import Dict, Any, List
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..services.asr_service import get_asr_service


from ..core.pipeline.chat_process import chat_process

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent


# 配置日志
logger = logging.getLogger("ws_api")

# 创建路由
router = APIRouter(tags=["WebSocket - 实时语音聊天"])


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        """初始化连接管理器"""
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """建立WebSocket连接

        Args:
            websocket: WebSocket连接
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket连接建立，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接

        Args:
            websocket: WebSocket连接
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket连接断开，当前连接数: {len(self.active_connections)}")

    async def send_json(self, websocket: WebSocket, data: Dict[str, Any]):
        """发送JSON数据

        Args:
            websocket: WebSocket连接
            data: 要发送的数据
        """
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {e}")
            # 移除失效的连接
            self.disconnect(websocket)


# 创建连接管理器实例
manager = ConnectionManager()


@router.websocket("/ws/realtime_chat")
async def realtime_chat_websocket_endpoint(websocket: WebSocket):
    """
    自动Pipeline WebSocket接口：语音输入 -> STT -> 自动触发LLM -> TTS -> 语音输出
    STT完成后自动调用pipeline进行完整处理
    """
    try:
        # 建立连接
        await manager.connect(websocket)
        logger.info("自动Pipeline WebSocket连接已建立")

        # 获取服务实例
        asr_service = get_asr_service()


        # 发送连接成功消息
        await manager.send_json(websocket, {
            "success": True,
            "message": "自动Pipeline WebSocket连接已建立",
            "description": "语音输入(STT)完成后自动触发LLM处理和TTS输出的完整pipeline"
        })

        # 初始化会话状态
        session_state = {
            "user_id": "anonymous",
            "model": "deepseek/deepseek-v3-0324",  # 默认使用deepseek模型
            "stream": True,
            "tts": True,
            "skip_db": False,
            "check_voiceprint": False,
            "only_register_user": False,
            "identify_unregistered": True
        }

        while True:
            # 接收消息
            data = await websocket.receive_text()

            try:
                # 解析JSON消息
                message = json.loads(data)
                action = message.get("action", "")

                if action == "config":
                    # 更新配置
                    config_data = message.get("data", {})
                    session_state.update({
                        "model": config_data.get("model", session_state["model"]),
                        "stream": config_data.get("stream", session_state["stream"]),
                        "tts": config_data.get("tts", session_state["tts"]),
                        "check_voiceprint": config_data.get("check_voiceprint", session_state["check_voiceprint"]),
                        "only_register_user": config_data.get("only_register_user", session_state["only_register_user"]),
                        "identify_unregistered": config_data.get("identify_unregistered", session_state["identify_unregistered"])
                    })
                    logger.info(f"自动Pipeline配置更新: {session_state}")
                    await manager.send_json(websocket, {
                        "success": True,
                        "message": "配置已更新",
                        "config": session_state
                    })

                elif action == "audio":
                    audio_data_base64 = message.get("data", {}).get("audio_data", "")
                    audio_format = message.get("data", {}).get("format", "wav")

                    if not audio_data_base64:
                        await manager.send_json(websocket, {
                            "success": False,
                            "error": "未接收到音频数据"
                        })
                        continue

                    # 解码音频数据
                    audio_data = base64.b64decode(audio_data_base64)
                    logger.info(f"接收到自动pipeline音频数据，格式: {audio_format}，大小: {len(audio_data)} 字节")

                    try:
                        # 第一步：执行STT
                        logger.info("开始STT处理...")
                        asr_result = asr_service.recognize(audio_data, audio_format=audio_format)

                        if not asr_result["success"]:
                            await manager.send_json(websocket, {
                                "success": False,
                                "error": f"语音识别失败: {asr_result['error']}"
                            })
                            continue

                        recognized_text = asr_result["text"]
                        logger.info(f"STT成功: '{recognized_text}'")

                        # 发送STT结果
                        await manager.send_json(websocket, {
                            "success": True,
                            "type": "stt_result",
                            "data": {
                                "transcription": recognized_text
                            }
                        })

                        # 第二步：如果STT成功，自动调用Pipeline进行LLM+TTS处理
                        if recognized_text.strip():
                            logger.info("STT成功，开始自动调用Pipeline...")

                            # 创建模拟的UploadFile对象用于pipeline处理
                            from io import BytesIO
                            from fastapi import UploadFile

                            # 创建BytesIO对象包装音频数据
                            audio_buffer = BytesIO(audio_data)
                            audio_buffer.seek(0)

                            # 创建UploadFile对象
                            audio_file = UploadFile(
                                filename="audio_input.wav",
                                file=audio_buffer
                            )

                            response = await chat_process.handle_request(
                                model=session_state["model"],
                                message=recognized_text,  # 使用STT识别的文本
                                role="user",
                                stream=session_state["stream"],
                                stt=False,  # STT已经完成，不需要再做
                                tts=session_state["tts"],  # 启用TTS
                                audio_file=None,  # 不传递音频文件，因为已经有了文本
                                user_id=session_state["user_id"]
                            )

                            # 处理pipeline响应
                            if session_state["stream"] and hasattr(response, 'body_iterator'):
                                # 流式响应处理
                                async for chunk in response.body_iterator:
                                    if chunk:
                                        chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
                                        # 解析SSE格式的数据
                                        if chunk_str.startswith('data: '):
                                            data_content = chunk_str[6:].strip()
                                            if data_content == '[DONE]':
                                                # 流式响应完成，发送complete消息并清除处理状态
                                                await manager.send_json(websocket, {
                                                    "success": True,
                                                    "type": "complete",
                                                    "message": "流式Pipeline处理完成"
                                                })
                                                logger.info("流式Pipeline处理完成")
                                                break
                                            try:
                                                chunk_data = json.loads(data_content)
                                                # 检查是否包含音频数据
                                                if 'audio' in chunk_data:
                                                    # 发送音频数据作为二进制
                                                    audio_bytes = base64.b64decode(chunk_data['audio'])
                                                    await websocket.send_bytes(audio_bytes)
                                                else:
                                                    # 发送其他数据作为JSON
                                                    await manager.send_json(websocket, {
                                                        "success": True,
                                                        "type": "stream_chunk",
                                                        "data": chunk_data
                                                    })
                                            except json.JSONDecodeError:
                                                continue
                            elif session_state["stream"] and hasattr(response, '__aiter__'):
                                # 处理异步生成器
                                async for chunk in response:
                                    if chunk:
                                        chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
                                        # 解析SSE格式的数据
                                        if chunk_str.startswith('data: '):
                                            data_content = chunk_str[6:].strip()
                                            if data_content == '[DONE]':
                                                # 流式响应完成，发送complete消息并清除处理状态
                                                await manager.send_json(websocket, {
                                                    "success": True,
                                                    "type": "complete",
                                                    "message": "流式Pipeline处理完成"
                                                })
                                                logger.info("流式Pipeline处理完成")
                                                break
                                            try:
                                                chunk_data = json.loads(data_content)
                                                # 发送给客户端
                                                await manager.send_json(websocket, {
                                                    "success": True,
                                                    "type": "stream_chunk",
                                                    "data": chunk_data
                                                })
                                            except json.JSONDecodeError:
                                                continue
                            else:
                                # 非流式响应
                                await manager.send_json(websocket, {
                                    "success": True,
                                    "type": "response",
                                    "data": response
                                })

                            # 发送处理完成消息，并清除处理状态标志
                            await manager.send_json(websocket, {
                                "success": True,
                                "type": "complete",
                                "message": "Pipeline处理完成"
                            })
                            logger.info("自动Pipeline处理完成")
                        else:
                            logger.info("STT结果为空，跳过Pipeline处理")
                            await manager.send_json(websocket, {
                                "success": True,
                                "type": "stt_result",
                                "data": {
                                    "transcription": recognized_text,
                                    "message": "STT结果为空"
                                }
                            })

                    except Exception as e:
                        logger.error(f"Pipeline处理失败: {str(e)}", exc_info=True)
                        await manager.send_json(websocket, {
                            "success": False,
                            "error": f"Pipeline处理失败: {str(e)}"
                        })

                else:
                    await manager.send_json(websocket, {
                        "success": False,
                        "error": f"不支持的动作: {action}"
                    })

            except json.JSONDecodeError:
                await manager.send_json(websocket, {
                    "success": False,
                    "error": "无效的JSON消息"
                })

            except Exception as e:
                logger.error(f"处理Pipeline WebSocket消息异常: {str(e)}", exc_info=True)
                await manager.send_json(websocket, {
                    "success": False,
                    "error": f"服务器内部错误: {str(e)}"
                })

    except WebSocketDisconnect:
        # 断开连接
        manager.disconnect(websocket)
        logger.info("Pipeline WebSocket连接已断开")

    except Exception as e:
        # 捕获其他异常
        logger.error(f"Pipeline WebSocket连接异常: {str(e)}", exc_info=True)
        manager.disconnect(websocket)
