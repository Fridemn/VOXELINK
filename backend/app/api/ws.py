"""
WebSocket API路由
"""

import logging
import json
import base64
import asyncio
from typing import Dict, Any, List
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..services.asr_service import get_asr_service
from ..services.vpr_service import get_vpr_service

from ..services.llm_service import get_llm_service
from ..core.pipeline.chat_process import chat_process

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent


def get_stt_settings() -> Dict[str, Any]:
    """获取STT配置"""
    # 使用后端统一配置系统
    try:
        from app.config.default import DEFAULT_CONFIG
        return DEFAULT_CONFIG.get("stt", {})
    except Exception as e:
        logger.warning(f"无法加载后端配置，使用空配置: {e}")
        return {}


# 配置日志
logger = logging.getLogger("ws_api")

# 创建路由
router = APIRouter(tags=["WebSocket"])


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


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket接口，支持实时语音识别和声纹识别
    """
    try:
        # 建立连接 - 只调用一次accept()
        await manager.connect(websocket)
        logger.info("WebSocket连接已建立")
        
        # 获取服务实例
        asr_service = get_asr_service()
        vpr_service = get_vpr_service()
        llm_service = get_llm_service()
        
        # 记录会话状态
        # 读取全局配置的llm.tts作为默认值
        settings = get_stt_settings()
        llm_config = settings.get("llm", {})
        session_state = {
            "audio_frames": [],
            "check_voiceprint": True,
            "only_register_user": False,
            "identify_unregistered": True,
            "user_token": "",  # 添加用户token字段
            "llm_api_url": "",  # 添加LLM API URL字段
            "llm_tts": llm_config.get("tts", False)  # 默认用配置文件
        }
        
        # 发送连接成功消息
        await manager.send_json(websocket, {
            "success": True,
            "message": "WebSocket连接已建立",
            "config": session_state
        })
        
        while True:
            # 接收消息
            data = await websocket.receive_text()
            
            try:
                # 解析JSON消息
                message = json.loads(data)
                action = message.get("action", "")
                
                # 根据动作类型处理
                if action == "config":
                    # 更新配置
                    config_data = message.get("data", {})
                    old_token = session_state.get("user_token", "")
                    session_state.update({
                        "check_voiceprint": config_data.get("check_voiceprint", session_state["check_voiceprint"]),
                        "only_register_user": config_data.get("only_register_user", session_state["only_register_user"]),
                        "identify_unregistered": config_data.get("identify_unregistered", session_state["identify_unregistered"]),
                        "user_token": config_data.get("user_token", session_state["user_token"]),  # 更新用户token
                        "llm_api_url": config_data.get("llm_api_url", session_state["llm_api_url"]),  # 更新LLM API URL
                        "llm_tts": config_data.get("llm_tts", session_state.get("llm_tts", True))  # 新增tts参数
                    })
                    
                    # 如果提供了LLM API URL，更新LLM服务配置
                    if session_state["llm_api_url"]:
                        llm_service.api_url = session_state["llm_api_url"]
                        logger.info(f"更新LLM API URL为: {session_state['llm_api_url']}")
                    
                    new_token = session_state.get("user_token", "")
                    logger.info(f"配置更新: 旧token长度: {len(old_token)}, 新token长度: {len(new_token)}")
                    
                    await manager.send_json(websocket, {
                        "success": True,
                        "message": "配置已更新",
                        "config": session_state
                    })
                elif action == "audio":
                    # 处理音频数据
                    audio_data_base64 = message.get("data", {}).get("audio_data", "")
                    audio_format = message.get("data", {}).get("format", "pcm")  # 获取音频格式，默认为pcm
                    
                    if not audio_data_base64:
                        await manager.send_json(websocket, {
                            "success": False,
                            "error": "未接收到音频数据"
                        })
                        continue
                      # 解码音频数据
                    audio_data = base64.b64decode(audio_data_base64)
                    
                    # 记录音频格式
                    logger.info(f"接收到音频数据，格式: {audio_format}，大小: {len(audio_data)} 字节")
                      # 如果需要检查声纹
                    user_info = {}
                    if session_state["check_voiceprint"]:
                        # 识别声纹
                        vpr_result = vpr_service.identify_voiceprint(audio_data)
                        
                        if vpr_result["success"]:
                            user_info = {
                                "user_id": vpr_result["user_id"],
                                "user_name": vpr_result["user_name"],
                                "similarity": vpr_result["similarity"]
                            }
                        elif session_state["only_register_user"]:
                            # 如果只识别已注册用户且声纹识别失败，则返回错误
                            await manager.send_json(websocket, {
                                "success": False,
                                "error": "未识别到已注册用户的声纹"
                            })
                            continue
                      # 执行语音识别 - 传入音频格式
                    asr_result = asr_service.recognize(audio_data, audio_format=audio_format)
                    
                    if asr_result["success"]:
                        # 包含语音检测结果（如果有）
                        speech_detection = {}
                        if "speech_detection" in asr_result:
                            speech_detection = {"speech_detection": asr_result["speech_detection"]}
                        
                        # 获取识别到的文本
                        recognized_text = asr_result["text"]
                        
                        # 添加调试日志
                        user_token = session_state.get("user_token", "")
                        logger.info(f"识别结果: '{recognized_text}', 用户token: '{user_token}', token长度: {len(user_token)}")
                        
                        # 如果有文本内容且配置了用户token，则发送给LLM
                        llm_response = None
                        if recognized_text.strip() and user_token.strip():
                            try:
                                logger.info(f"准备调用LLM，文本: '{recognized_text}', token: '{user_token[:20]}...'")
                                llm_response = await llm_service.send_to_llm(
                                    recognized_text,
                                    user_token,
                                    tts=session_state.get("llm_tts", False)
                                )
                                logger.info(f"LLM调用成功，响应: {llm_response}")
                            except Exception as e:
                                logger.error(f"LLM调用失败: {e}")
                        else:
                            logger.info(f"跳过LLM调用 - 文本为空: {not recognized_text.strip()}, token为空: {not user_token.strip()}")
                        
                        # 返回识别结果
                        response_data = {
                            "success": True,
                            "text": recognized_text,
                            **user_info,
                            **speech_detection  # 添加语音检测信息
                        }
                        
                        # 如果有LLM响应，也包含在结果中
                        if llm_response:
                            response_data["llm_response"] = llm_response
                        
                        await manager.send_json(websocket, response_data)
                    else:
                        await manager.send_json(websocket, {
                            "success": False,
                            "error": asr_result["error"]
                        })
                        
                elif action == "register_voiceprint":
                    # 注册声纹
                    reg_data = message.get("data", {})
                    user_id = reg_data.get("user_id", "")
                    user_name = reg_data.get("user_name", "")
                    audio_data_base64 = reg_data.get("audio_data", "")
                    
                    if not user_id or not audio_data_base64:
                        await manager.send_json(websocket, {
                            "success": False,
                            "error": "缺少用户ID或音频数据"
                        })
                        continue
                    
                    # 解码音频数据
                    audio_data = base64.b64decode(audio_data_base64)
                    
                    # 注册声纹
                    result = vpr_service.register_voiceprint(user_id, user_name or "未命名用户", audio_data)
                    
                    # 返回结果
                    await manager.send_json(websocket, result)
                    
                elif action == "identify_voiceprint":
                    # 识别声纹
                    audio_data_base64 = message.get("data", {}).get("audio_data", "")
                    
                    if not audio_data_base64:
                        await manager.send_json(websocket, {
                            "success": False,
                            "error": "未接收到音频数据"
                        })
                        continue
                    
                    # 解码音频数据
                    audio_data = base64.b64decode(audio_data_base64)
                    
                    # 识别声纹
                    result = vpr_service.identify_voiceprint(audio_data)
                    
                    # 返回结果
                    await manager.send_json(websocket, result)
                    
                elif action == "list_voiceprints":
                    # 获取声纹列表
                    result = vpr_service.list_voiceprints()
                    
                    # 返回结果
                    await manager.send_json(websocket, result)
                    
                elif action == "remove_voiceprint":
                    # 删除声纹
                    user_id = message.get("data", {}).get("user_id", "")
                    
                    if not user_id:
                        await manager.send_json(websocket, {
                            "success": False,
                            "error": "缺少用户ID"
                        })
                        continue
                    
                    # 删除声纹
                    result = vpr_service.remove_voiceprint(user_id)
                    
                    # 返回结果
                    await manager.send_json(websocket, result)
                    
                elif action == "compare_voiceprints":
                    # 比对声纹
                    compare_data = message.get("data", {})
                    audio_data1_base64 = compare_data.get("audio_data1", "")
                    audio_data2_base64 = compare_data.get("audio_data2", "")
                    
                    if not audio_data1_base64 or not audio_data2_base64:
                        await manager.send_json(websocket, {
                            "success": False,
                            "error": "缺少音频数据"
                        })
                        continue
                    
                    # 解码音频数据
                    audio_data1 = base64.b64decode(audio_data1_base64)
                    audio_data2 = base64.b64decode(audio_data2_base64)
                    
                    # 比对声纹
                    result = vpr_service.compare_voiceprints(audio_data1, audio_data2)
                    
                    # 返回结果
                    await manager.send_json(websocket, result)
                    
                elif action == "ping":
                    # 心跳检测
                    await manager.send_json(websocket, {
                        "success": True,
                        "action": "pong",
                        "timestamp": message.get("data", {}).get("timestamp", 0)
                    })
                    
                else:
                    # 未知动作
                    await manager.send_json(websocket, {
                        "success": False,
                        "error": f"未知动作: {action}"
                    })
                    
            except json.JSONDecodeError:
                await manager.send_json(websocket, {
                    "success": False,
                    "error": "无效的JSON消息"
                })
                
            except Exception as e:
                logger.error(f"处理WebSocket消息异常: {str(e)}", exc_info=True)
                await manager.send_json(websocket, {
                    "success": False,
                    "error": f"服务器内部错误: {str(e)}"
                })
                
    except WebSocketDisconnect:
        # 断开连接
        manager.disconnect(websocket)
        logger.info("WebSocket连接已断开")
        
    except Exception as e:
        # 捕获其他异常
        logger.error(f"WebSocket连接异常: {str(e)}", exc_info=True)
        manager.disconnect(websocket)


@router.websocket("/ws/auto_pipeline")
async def auto_pipeline_websocket_endpoint(websocket: WebSocket):
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
            "skip_db": True,  # 默认跳过数据库操作
            "check_voiceprint": False,  # 默认不检查声纹
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
                    # 处理音频数据：STT -> 自动Pipeline
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

                            # 调用pipeline处理 - 使用STT结果作为文本消息
                            response = await chat_process.handle_request(
                                model=session_state["model"],
                                message=recognized_text,  # 使用STT识别的文本
                                history_id=None,  # 会自动创建
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

                            logger.info("自动Pipeline处理完成")
                        else:
                            logger.info("STT结果为空，跳过Pipeline处理")
                            await manager.send_json(websocket, {
                                "success": True,
                                "type": "complete",
                                "message": "语音识别结果为空"
                            })

                    except Exception as e:
                        logger.error(f"自动Pipeline处理失败: {str(e)}", exc_info=True)
                        await manager.send_json(websocket, {
                            "success": False,
                            "error": f"处理失败: {str(e)}"
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
                logger.error(f"处理自动Pipeline WebSocket消息异常: {str(e)}", exc_info=True)
                await manager.send_json(websocket, {
                    "success": False,
                    "error": f"服务器内部错误: {str(e)}"
                })

    except WebSocketDisconnect:
        # 断开连接
        manager.disconnect(websocket)
        logger.info("自动Pipeline WebSocket连接已断开")

    except Exception as e:
        # 捕获其他异常
        logger.error(f"自动Pipeline WebSocket连接异常: {str(e)}", exc_info=True)
        manager.disconnect(websocket)
    """
    Pipeline WebSocket接口：语音输入 -> STT -> LLM -> TTS -> 语音输出
    支持完整的语音对话流程
    """
    try:
        # 建立连接
        await manager.connect(websocket)
        logger.info("Pipeline WebSocket连接已建立")

        # 获取服务实例
        asr_service = get_asr_service()

        # 发送连接成功消息
        await manager.send_json(websocket, {
            "success": True,
            "message": "Pipeline WebSocket连接已建立",
            "description": "支持语音输入(STT) -> LLM处理 -> 语音输出(TTS)的完整pipeline"
        })

        # 初始化会话状态
        session_state = {
            "user_id": "anonymous",
            "model": "deepseek/deepseek-v3-0324",  # 默认使用deepseek模型
            "stream": True,
            "tts": True,
            "skip_db": True  # 默认跳过数据库操作
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
                        "tts": config_data.get("tts", session_state["tts"])
                    })
                    logger.info(f"Pipeline配置更新: {session_state}")
                    await manager.send_json(websocket, {
                        "success": True,
                        "message": "配置已更新",
                        "config": session_state
                    })

                elif action == "audio":
                    # 处理音频数据进行完整pipeline
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
                    logger.info(f"接收到pipeline音频数据，格式: {audio_format}，大小: {len(audio_data)} 字节")

                    # 创建模拟的UploadFile对象
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

                    try:
                        # 使用chat_process进行完整pipeline处理
                        response = await chat_process.handle_request(
                            model=session_state["model"],
                            message="",  # 文本消息为空，因为我们用音频
                            history_id=None,  # 会自动创建
                            role="user",
                            stream=session_state["stream"],
                            stt=True,  # 启用STT
                            tts=session_state["tts"],  # 启用TTS
                            audio_file=audio_file,
                            user_id=session_state["user_id"]
                        )

                        # 如果是流式响应，处理SSE数据
                        if session_state["stream"] and hasattr(response, 'body_iterator'):
                            # 流式响应处理
                            async for chunk in response.body_iterator:
                                if chunk:
                                    chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
                                    # 解析SSE格式的数据
                                    if chunk_str.startswith('data: '):
                                        data_content = chunk_str[6:].strip()
                                        if data_content == '[DONE]':
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
