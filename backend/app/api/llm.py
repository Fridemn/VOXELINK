"""
llm.py
负责与大语言模型相关的API接口，如对话、历史记录等。
- 提供与LLM交互的RESTful接口。
- 依赖消息、历史、流程等子模块。
"""

from typing import Optional

import os
import traceback
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends, Form, Query, UploadFile, File
from loguru import logger

from .. import app_config
from ..core.llm.message import MessageRole
from ..core.db.db_history import db_message_history
from ..core.pipeline.chat_process import chat_process


api_llm = APIRouter()

# 创建音频文件存储目录
AUDIO_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "audio")
os.makedirs(AUDIO_STORAGE_DIR, exist_ok=True)


class ChatRequest(BaseModel):
    model: Optional[str] = None
    message: str
    role: MessageRole = MessageRole.USER


class UnifiedChatRequest(BaseModel):
    """统一的聊天请求模型"""

    model: Optional[str] = None
    message: Optional[str] = ""  # 文本消息
    role: MessageRole = MessageRole.USER
    stream: bool = False  # 是否流式输出


# 统一的聊天接口
@api_llm.post("/chat")
async def unified_chat(
    model: Optional[str] = Form(None),
    message: Optional[str] = Form(""),
    role: MessageRole = Form(MessageRole.USER),
    stream: bool = Form(False),
    tts: bool = Form(False),  # 添加TTS开关
    audio_file: Optional[UploadFile] = File(None),  # 添加音频文件上传
):
    """
    统一的聊天接口，支持文本聊天、流式输出、语音合成和语音输入
    """
    logger.info(f"接收到聊天请求: stream={stream}, tts={tts}, has_audio={audio_file is not None}")
    try:
        # 使用默认用户ID
        user_id = "anonymous"

        # 确定是否需要STT
        stt = audio_file is not None
        
        # 使用聊天流水线处理请求
        return await chat_process.handle_request(
            model=model,
            message=message,
            role=role,
            stream=stream,
            stt=stt,
            tts=tts,
            audio_file=audio_file,
            user_id=user_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"统一聊天接口异常: {str(e)}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"处理请求失败: {str(e)}")


# ------------------------------
# 历史记录部分
# ------------------------------


# @api_llm.get("/history")
# async def get_user_history():
#     """获取历史记录"""
#     try:
#         message_count = await db_message_history.get_message_count()
#         return {
#             "message_count": message_count,
#             "context_window": db_message_history.context_window
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")


@api_llm.get("/history/messages")
async def get_history_messages():
    """获取历史消息"""
    try:
        # 获取历史消息
        messages = await db_message_history.get_history()

        # 返回消息列表，处理可能的序列化错误
        message_dicts = []
        for msg in messages:
            try:
                message_dict = msg.dict()
                # 确保message_id设置正确
                if not message_dict.get("message_id"):
                    message_dict["message_id"] = msg.message_id
                message_dicts.append(message_dict)
            except Exception as e:
                logger.error(f"消息序列化失败: {str(e)}")
                # 创建简化版消息
                simple_msg = {
                    "message_id": msg.message_id,
                    "message_str": msg.message_str,
                    "timestamp": msg.timestamp,
                    "sender": {"role": "unknown", "nickname": None},
                    "components": [],
                }

                # 尝试添加角色信息
                if hasattr(msg, "sender"):
                    if hasattr(msg.sender, "role"):
                        simple_msg["sender"]["role"] = str(msg.sender.role)
                    if hasattr(msg.sender, "nickname"):
                        simple_msg["sender"]["nickname"] = msg.sender.nickname

                message_dicts.append(simple_msg)

        return {"messages": message_dicts, "count": len(message_dicts)}
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"获取历史消息失败: {str(e)}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"获取历史消息失败: {str(e)}")


@api_llm.delete("/history")
async def clear_history():
    """清空历史记录"""
    try:
        success = await db_message_history.clear_history()
        return {"success": success}
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"清空历史记录失败: {str(e)}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"清空历史记录失败: {str(e)}")






@api_llm.get("/available-models")
async def get_available_models():
    """获取可用的模型列表"""
    try:
        llm_config = app_config["llm"]
    except Exception:
        return {"available-models": []}

    result = set()
    for k, v in llm_config.items():
        if k.endswith("_models") and isinstance(v, list):
            result.update(v)
        elif k == "default_model" and isinstance(v, str):
            result.add(v)
    return {"available-models": sorted(list(result))}
