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
from fastapi import APIRouter, HTTPException, Depends, Form, Query
from loguru import logger

from .. import app_config
from ..core.llm.message import MessageRole
from ..core.db.db_history import db_message_history
from ..core.pipeline.chat_process import chat_process
from ..core.pipeline.function_process import function_process
from ..core.pipeline.summarize_process import summarize_process
from ..core.funcall.function_handler import function_handler


api_llm = APIRouter()

# 创建音频文件存储目录
AUDIO_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "audio")
os.makedirs(AUDIO_STORAGE_DIR, exist_ok=True)


class ChatRequest(BaseModel):
    model: Optional[str] = None
    message: str
    role: MessageRole = MessageRole.USER


class HistoryUpdateRequest(BaseModel):
    title: str


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
):
    """
    统一的聊天接口，支持文本聊天、流式输出和语音合成
    """
    logger.info(f"接收到聊天请求: stream={stream}, tts={tts}")
    try:
        # 使用默认用户ID
        user_id = "anonymous"
        history_id = await db_message_history.get_user_history_id(user_id)

        
        # 检查是否是函数调用命令
        if message:
            function_call = function_handler.detect_function_call_intent(message)
            if function_call:
                function_name, result, need_llm = function_handler.handle_function_call(function_call)

                function_message = function_handler.create_function_message(history_id, function_name, result)

                await db_message_history.add_message(history_id, function_message)

                need_llm = function_call.get("need_llm", need_llm)

                if need_llm:
                    return await function_process.handle_function_result(
                        model=model,
                        function_name=function_name,
                        result=result,
                        history_id=history_id,
                        stream=stream,
                        tts=tts, # 传递tts参数
                        user_id=user_id,
                        function_message=function_message,
                    )
                else:
                    if stream:
                        return function_process.create_function_stream_response(function_name, result)
                    else:
                        return {
                            "success": True,
                            "function_call": {"name": function_name, "result": result},
                            "message_id": function_message.message_id,
                        }

        # 使用聊天流水线处理请求
        return await chat_process.handle_request(
            model=model,
            message=message,
            history_id=history_id,
            role=role,
            stream=stream,
            stt=False,
            tts=tts,
            audio_file=None,
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


@api_llm.get("/history")
async def get_user_history():
    """获取历史记录"""
    try:
        user_id = "anonymous"
        history = await db_message_history.get_user_history(user_id)

        if not history:
            # 如果用户没有历史记录，创建一个新的
            history_id = await db_message_history.create_history(user_id)
            return {"history_id": history_id}

        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")


@api_llm.get("/history/messages")
async def get_history_messages():
    """获取历史消息"""
    try:
        user_id = "anonymous"

        # 先获取用户的历史ID
        history = await db_message_history.get_user_history(user_id)
        if not history:
            return {"history_id": "", "messages": [], "count": 0}

        history_id = history["history_id"]
        logger.info(f"请求用户 {user_id} 的历史记录: {history_id}")

        # 使用db_message_history获取格式化消息
        messages = await db_message_history.get_history(history_id)

        # 返回消息列表，处理可能的序列化错误
        message_dicts = []
        for msg in messages:
            try:
                message_dict = msg.dict()
                # 确保history_id设置正确
                if not message_dict.get("history_id"):
                    message_dict["history_id"] = history_id
                message_dicts.append(message_dict)
            except Exception as e:
                logger.error(f"消息序列化失败: {str(e)}")
                # 创建简化版消息
                simple_msg = {
                    "message_id": msg.message_id,
                    "history_id": history_id,
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

        return {"history_id": history_id, "messages": message_dicts, "count": len(message_dicts)}
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"获取历史消息失败: {str(e)}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"获取历史消息失败: {str(e)}")


@api_llm.delete("/history")
async def clear_history():
    """清空历史记录"""
    try:
        user_id = "anonymous"

        # 先获取用户的历史ID
        history = await db_message_history.get_user_history(user_id)
        if not history:
            return {"success": True}

        history_id = history["history_id"]
        success = await db_message_history.delete_history(history_id)
        return {"success": success}
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"清空历史记录失败: {str(e)}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"清空历史记录失败: {str(e)}")


# ------------------------------
# 历史记录更新部分
# ------------------------------


@api_llm.put("/history/title")
async def update_history_title(request: HistoryUpdateRequest):
    """更新历史记录标题"""
    try:
        user_id = "anonymous"

        # 先获取用户的历史ID
        history = await db_message_history.get_user_history(user_id)
        if not history:
            raise HTTPException(status_code=404, detail="历史记录不存在")

        history_id = history["history_id"]
        success = await db_message_history.update_history_title(history_id, request.title)
        if not success:
            raise HTTPException(status_code=404, detail="更新历史记录标题失败")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"更新历史记录标题失败: {str(e)}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"更新历史记录标题失败: {str(e)}")


@api_llm.post("/history/summarize")
async def summarize_history_title():
    """自动总结历史记录内容并更新标题"""
    try:
        user_id = "anonymous"

        # 先获取用户的历史ID
        history = await db_message_history.get_user_history(user_id)
        if not history:
            raise HTTPException(status_code=404, detail="历史记录不存在")

        history_id = history["history_id"]

        # 使用摘要流水线处理请求
        result = await summarize_process.generate_history_title(history_id=history_id, user_id=user_id)

        # 检查处理结果，确保没有残留临时的history_id
        if result.get("temporary_history_id"):
            # 删除临时创建的历史记录
            temp_history_id = result.pop("temporary_history_id")
            await db_message_history.completely_delete_history(temp_history_id)
            logger.info(f"清理了临时历史记录: {temp_history_id}")

        # 清理孤立和无用户关联的历史记录
        await cleanup_all_orphaned_histories(user_id, history_id)

        return result

    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"总结历史记录标题失败: {str(e)}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"总结历史记录标题失败: {str(e)}")


# 重写清理函数，增加对无用户关联记录的清理
async def cleanup_all_orphaned_histories(user_id: str, current_history_id: str):
    """清理所有孤立的历史记录，包括与用户关联及无关联的记录"""
    from app.models.chat import ChatHistory

    try:
        # 清理第一部分：该用户除了当前历史记录外的所有其他历史记录
        user_orphaned_histories = await ChatHistory.filter(user_id=user_id).exclude(history_id=current_history_id).all()

        # 删除找到的所有用户关联的孤立历史记录
        for history in user_orphaned_histories:
            orphan_id = str(history.history_id)
            await db_message_history.completely_delete_history(orphan_id)
            logger.info(f"清理了用户 {user_id} 的孤立历史记录: {orphan_id}")

        # 清理第二部分：所有无用户关联的历史记录（user_id为NULL）
        null_user_histories = await ChatHistory.filter(user_id=None).all()

        # 删除找到的所有无用户关联的历史记录
        for history in null_user_histories:
            orphan_id = str(history.history_id)
            await db_message_history.completely_delete_history(orphan_id)
            logger.info(f"清理了无用户关联的历史记录: {orphan_id}")

        total_cleaned = len(user_orphaned_histories) + len(null_user_histories)
        if total_cleaned > 0:
            logger.info(f"共清理了 {total_cleaned} 条孤立历史记录")

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"清理孤立历史记录时出错: {str(e)}\n{error_trace}")


# 添加定期清理接口
@api_llm.post("/admin/cleanup-histories")
async def admin_cleanup_histories():
    """清理所有孤立的历史记录"""
    try:
        from app.models.chat import ChatHistory

        # 清理所有无用户关联的历史记录
        null_user_histories = await ChatHistory.filter(user_id=None).all()

        # 删除找到的所有无用户关联的历史记录
        for history in null_user_histories:
            orphan_id = str(history.history_id)
            await db_message_history.completely_delete_history(orphan_id)

        return {
            "success": True,
            "cleaned_count": len(null_user_histories),
            "message": f"成功清理了 {len(null_user_histories)} 条无用户关联的历史记录",
        }

    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"清理历史记录失败: {str(e)}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"清理历史记录失败: {str(e)}")


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
