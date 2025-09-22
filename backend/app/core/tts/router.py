#!/usr/bin/env python3
"""
GPT-SoVITS 路由模块
包含所有API路由和WebSocket端点
"""

import json
import logging
import os
import sys
import traceback
import warnings
from typing import Optional, List, Union, Dict
import tempfile
import base64
import io
import time
import asyncio
from pathlib import Path

import torch
import torchaudio
import librosa
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field

# 导入我们的核心推理模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core_inference import (
    get_tts_wav,
    load_models,
    change_sovits_weights,
    change_gpt_weights,
    dict_language
)

# 配置日志
logger = logging.getLogger(__name__)

# 英文到中文的参数映射
LANGUAGE_MAP = {
    "chinese": "中文",
    "english": "英文",
    "japanese": "日文",
    "cantonese": "粤语",
    "korean": "韩文",
    "chinese_english": "中英混合",
    "japanese_english": "日英混合",
    "cantonese_english": "粤英混合",
    "korean_english": "韩英混合",
    "multilingual": "多语种混合",
    "multilingual_cantonese": "多语种混合(粤语)",
    "auto": "多语种混合"
}

CUT_METHOD_MAP = {
    "no_cut": "不切",
    "cut_by_4_sentences": "凑四句一切",
    "cut_by_50_chars": "凑50字一切",
    "cut_by_chinese_period": "按中文句号。切",
    "cut_by_english_period": "按英文句号.切",
    "cut_by_punctuation": "按标点符号切"
}

def map_language_param(language_en):
    """映射英文语言参数到中文"""
    return LANGUAGE_MAP.get(language_en, language_en)

def map_cut_method_param(cut_method_en):
    """映射英文切分方式参数到中文"""
    return CUT_METHOD_MAP.get(cut_method_en, cut_method_en)

# WebSocket连接管理器
class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, token: str):
        await websocket.accept()
        if token not in self.active_connections:
            self.active_connections[token] = []
        self.active_connections[token].append(websocket)
        logger.info(f"WebSocket连接建立，token: {token}")

    def disconnect(self, websocket: WebSocket, token: str):
        if token in self.active_connections:
            if websocket in self.active_connections[token]:
                self.active_connections[token].remove(websocket)
            if not self.active_connections[token]:
                del self.active_connections[token]
        logger.info(f"WebSocket连接断开，token: {token}")

    async def send_audio_to_token(self, token: str, audio_data: dict):
        if token in self.active_connections:
            disconnected = []
            for connection in self.active_connections[token]:
                try:
                    await connection.send_json(audio_data)
                except Exception as e:
                    logger.warning(f"发送音频数据失败: {e}")
                    disconnected.append(connection)

            # 移除断开的连接
            for conn in disconnected:
                self.disconnect(conn, token)

# 创建WebSocket管理器实例
websocket_manager = WebSocketManager()

# 数据模型定义
class TTSRequest(BaseModel):
    """TTS 合成请求模型"""
    text: str = Field(..., description="需要合成的文本")
    text_language: str = Field("chinese", description="需要合成的语种")
    prompt_text: str = Field("", description="参考音频的文本")
    prompt_language: str = Field("chinese", description="参考音频的语种")
    how_to_cut: str = Field("no_cut", description="文本切分方式")
    top_k: int = Field(20, ge=1, le=100, description="top_k 参数")
    top_p: float = Field(0.6, ge=0, le=1, description="top_p 参数")
    temperature: float = Field(0.6, ge=0, le=1, description="temperature 参数")
    ref_free: bool = Field(False, description="是否使用无参考文本模式")
    speed: float = Field(1.0, ge=0.6, le=1.65, description="语速调整")
    if_freeze: bool = Field(False, description="是否直接对上次合成结果调整语速和音色")
    sample_steps: int = Field(8, description="采样步数")
    if_sr: bool = Field(False, description="是否进行超分")
    pause_second: float = Field(0.3, ge=0.1, le=0.5, description="句间停顿秒数")

class ModelInfo(BaseModel):
    """模型信息模型"""
    sovits_models: List[str]
    gpt_models: List[str]
    current_sovits: str
    current_gpt: str
    version: str
    supported_languages: List[str]

class ModelSwitchRequest(BaseModel):
    """模型切换请求模型"""
    sovits_path: Optional[str] = None
    gpt_path: Optional[str] = None

# 创建路由器
router = APIRouter()

# 全局变量存储当前模型路径和状态
current_sovits_path = ""
current_gpt_path = ""
model_loaded = False
config = None  # 将在main.py中设置

def set_config(global_config):
    """设置全局配置"""
    global config, model_loaded, current_sovits_path, current_gpt_path
    config = global_config
    
    # 如果模型还没有加载，加载默认模型
    if not model_loaded:
        try:
            # 获取项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            
            default_sovits = config["default_models"]["sovits_path"]
            default_gpt = config["default_models"]["gpt_path"]
            
            # 如果路径不是绝对路径，则相对于项目根目录解析
            if not os.path.isabs(default_sovits):
                default_sovits = os.path.join(project_root, default_sovits)
            if not os.path.isabs(default_gpt):
                default_gpt = os.path.join(project_root, default_gpt)
            
            # 检查模型文件是否存在
            if not os.path.exists(default_sovits):
                logger.warning(f"SoVITS模型文件不存在: {default_sovits}")
                return
            if not os.path.exists(default_gpt):
                logger.warning(f"GPT模型文件不存在: {default_gpt}")
                return
            
            logger.info(f"正在加载默认模型 - SoVITS: {default_sovits}, GPT: {default_gpt}")
            load_models(default_gpt, default_sovits)
            
            # 重新加载SoVITS模型以确保正确的模型版本检测
            from core_inference import change_sovits_weights
            change_sovits_weights(default_sovits)
            
            current_sovits_path = default_sovits
            current_gpt_path = default_gpt
            model_loaded = True
            logger.info("TTS模型加载成功")
        except Exception as e:
            logger.error(f"加载TTS模型失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

@router.post("/models/switch", summary="切换模型")
async def switch_models(request: ModelSwitchRequest):
    """切换 SoVITS 或 GPT 模型"""
    global current_sovits_path, current_gpt_path, model_loaded

    try:
        success_messages = []

        if request.sovits_path:
            # 检查文件是否存在
            if not os.path.exists(request.sovits_path):
                raise HTTPException(status_code=404, detail=f"SoVITS 模型文件不存在: {request.sovits_path}")

            # 更新环境变量
            os.environ["SOVITS_PATH"] = request.sovits_path

            logger.info(f"切换 SoVITS 模型到: {request.sovits_path}")
            change_sovits_weights(request.sovits_path)
            current_sovits_path = request.sovits_path
            success_messages.append(f"SoVITS 模型切换成功: {request.sovits_path}")

            # 更新配置文件
            config["default_models"]["sovits_path"] = request.sovits_path

        if request.gpt_path:
            # 检查文件是否存在
            if not os.path.exists(request.gpt_path):
                raise HTTPException(status_code=404, detail=f"GPT 模型文件不存在: {request.gpt_path}")

            # 更新环境变量
            os.environ["GPT_PATH"] = request.gpt_path

            logger.info(f"切换 GPT 模型到: {request.gpt_path}")
            change_gpt_weights(request.gpt_path)
            current_gpt_path = request.gpt_path
            success_messages.append(f"GPT 模型切换成功: {request.gpt_path}")

            # 更新配置文件
            config["default_models"]["gpt_path"] = request.gpt_path

        if not request.sovits_path and not request.gpt_path:
            raise HTTPException(status_code=400, detail="请至少指定一个模型路径")

        model_loaded = True

        return {
            "message": "; ".join(success_messages),
            "current_sovits": current_sovits_path,
            "current_gpt": current_gpt_path,
            "status": "success"
        }

    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.error(f"模型文件缺失: {str(e)}")
        raise HTTPException(status_code=404, detail=f"模型文件缺失: {str(e)}")
    except Exception as e:
        logger.error(f"模型切换失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"模型切换失败: {str(e)}")

@router.get("/models/status", summary="获取模型状态")
async def get_model_status():
    """获取当前模型加载状态"""
    global current_sovits_path, current_gpt_path, model_loaded

    return {
        "model_loaded": model_loaded,
        "current_sovits": current_sovits_path,
        "current_gpt": current_gpt_path,
        "sovits_exists": os.path.exists(current_sovits_path) if current_sovits_path else False,
        "gpt_exists": os.path.exists(current_gpt_path) if current_gpt_path else False
    }

@router.post("/tts", summary="语音合成")
async def text_to_speech(
    background_tasks: BackgroundTasks,
    text: str = Form(..., description="需要合成的文本"),
    character: str = Form(None, description="角色名称"),
    mood: str = Form(None, description="情绪"),
    text_language: str = Form(None, description="合成文本的语言"),
    how_to_cut: str = Form(None, description="文本切分方式"),
    token: str = Form(None, description="WebSocket推送token，如果提供则通过WebSocket推送音频")
):
    """
    执行语音合成

    - **text**: 需要合成的文本
    - **character**: 角色名称（可选，默认使用配置文件）
    - **mood**: 情绪（可选，默认使用角色的默认情绪或normal）
    - **text_language**: 合成文本的语言（可选，默认使用配置文件）
    - **how_to_cut**: 文本切分方式（可选，默认使用配置文件）
    - **token**: WebSocket推送token，如果提供则通过WebSocket推送音频
    """
    try:
        # 检查模型是否已加载
        if not model_loaded:
            raise HTTPException(status_code=503, detail="模型尚未加载，请先切换模型或重启服务")

        # 从配置文件读取推理参数
        inference_config = config.get("inference", {})
        
        # 从全局配置中获取角色配置
        from app.config.default import DEFAULT_CONFIG
        global_config = DEFAULT_CONFIG
        characters_config = global_config.get("characters", {})

        # 获取默认角色和情绪
        default_character = character or inference_config.get("default_character", "march7")
        character_config = characters_config.get(default_character, {})

        if not character_config:
            # 如果找不到指定角色，使用第一个可用角色
            if characters_config:
                default_character = list(characters_config.keys())[0]
                character_config = characters_config[default_character]
            else:
                raise HTTPException(status_code=404, detail="未找到任何角色配置")

        # 获取情绪配置
        default_mood = mood or character_config.get("default_mood", "normal")
        moods_config = character_config.get("moods", {})
        mood_config = moods_config.get(default_mood)

        if not mood_config:
            # 如果找不到指定情绪，尝试使用normal
            mood_config = moods_config.get("normal")
            if not mood_config and moods_config:
                # 如果连normal都没有，使用第一个可用情绪
                mood_config = list(moods_config.values())[0]
            if not mood_config:
                raise HTTPException(status_code=404, detail=f"角色 {default_character} 未找到情绪配置")

        # 获取参考音频路径和文本
        ref_audio_path = mood_config.get("audio_path")
        prompt_text = mood_config.get("prompt_text", "")
        prompt_language_en = mood_config.get("language", "chinese")
        prompt_language = map_language_param(prompt_language_en)

        if not ref_audio_path or not os.path.exists(ref_audio_path):
            raise HTTPException(status_code=404, detail=f"参考音频文件不存在: {ref_audio_path}")

        # 其他参数从配置文件读取并映射
        text_language_en = text_language or inference_config.get("default_language", "chinese")
        text_language = map_language_param(text_language_en)

        how_to_cut_en = how_to_cut or inference_config.get("default_how_to_cut", "no_cut")
        how_to_cut = map_cut_method_param(how_to_cut_en)

        # 从配置文件读取固定参数
        top_k = inference_config.get("default_top_k", 15)
        top_p = inference_config.get("default_top_p", 1.0)
        temperature = inference_config.get("default_temperature", 1.0)
        ref_free = inference_config.get("default_ref_free", False)
        speed = inference_config.get("default_speed", 1.0)
        if_freeze = inference_config.get("default_if_freeze", False)
        sample_steps = inference_config.get("default_sample_steps", 8)
        if_sr = inference_config.get("default_if_sr", False)
        pause_second = inference_config.get("default_pause_second", 0.3)

        logger.info(f"使用角色: {default_character}, 情绪: {default_mood}, 参考音频: {ref_audio_path}")

        # 调用我们的 TTS 函数
        result_generator = get_tts_wav(
            ref_wav_path=ref_audio_path,
            prompt_text=prompt_text,
            prompt_language=prompt_language,
            text=text,
            text_language=text_language,
            how_to_cut=how_to_cut,
            top_k=top_k,
            top_p=top_p,
            temperature=temperature,
            ref_free=ref_free,
            speed=speed,
            if_freeze=if_freeze,
            inp_refs=None,  # 简化版本，不支持多个参考音频
            sample_steps=sample_steps,
            if_sr=if_sr,
            pause_second=pause_second,
        )

        # 获取生成的音频
        sr, audio_data = next(result_generator)

        if sr is None or audio_data is None:
            raise HTTPException(status_code=500, detail="音频生成失败")

        # 如果提供了token，则通过WebSocket推送音频
        if token and token.strip():
            try:
                # 将音频数据转换为 Base64 (OGG)
                buffer = io.BytesIO()
                if isinstance(audio_data, np.ndarray):
                    audio_tensor = torch.from_numpy(audio_data.astype(np.float32)) / 32767.0
                else:
                    audio_tensor = audio_data
                # 保存为ogg格式
                torchaudio.save(buffer, audio_tensor.unsqueeze(0), sr, format="ogg", encoding="vorbis")
                buffer.seek(0)
                # 编码为 Base64
                audio_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                # 构建音频数据包
                audio_packet = {
                    "type": "audio",
                    "timestamp": int(time.time() * 1000),  # 毫秒时间戳
                    "audio_base64": audio_base64,
                    "sample_rate": sr,
                    "character": default_character,
                    "mood": default_mood,
                    "text": text,
                    "message": "音频生成成功",
                    "audio_format": "ogg"
                }
                # 通过WebSocket推送音频
                await websocket_manager.send_audio_to_token(token, audio_packet)
                return {
                    "message": "音频已通过WebSocket推送",
                    "token": token,
                    "timestamp": audio_packet["timestamp"],
                    "character": default_character,
                    "mood": default_mood
                }
            except Exception as e:
                logger.error(f"WebSocket推送失败: {str(e)}")
                # 如果WebSocket推送失败，继续执行正常的文件返回逻辑
        # 将音频数据保存到临时文件（OGG）
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_output:
            # 确保音频数据是正确的格式
            if isinstance(audio_data, np.ndarray):
                # 转换为 torch tensor
                audio_tensor = torch.from_numpy(audio_data.astype(np.float32)) / 32767.0
            else:
                audio_tensor = audio_data
            # 保存音频文件为ogg
            torchaudio.save(temp_output.name, audio_tensor.unsqueeze(0), sr, format="ogg", encoding="vorbis")
            output_path = temp_output.name
        # 定义清理函数
        def cleanup_files():
            try:
                if os.path.exists(output_path):
                    os.unlink(output_path)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")
        # 添加后台任务来清理文件
        background_tasks.add_task(cleanup_files)
        # 返回音频文件（OGG）
        return FileResponse(
            output_path,
            media_type="audio/ogg",
            filename="generated_audio.ogg"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS 合成失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"TTS 合成失败: {str(e)}")

@router.post("/tts/base64", summary="语音合成 (Base64)")
async def text_to_speech_base64(
    text: str = Form(..., description="需要合成的文本"),
    character: str = Form(None, description="角色名称"),
    mood: str = Form(None, description="情绪"),
    text_language: str = Form(None, description="合成文本的语言"),
    how_to_cut: str = Form(None, description="文本切分方式"),
    token: str = Form(None, description="WebSocket推送token，如果提供则通过WebSocket推送音频")
):
    """
    执行语音合成并返回 Base64 编码的音频数据

    - **text**: 需要合成的文本
    - **character**: 角色名称（可选，默认使用配置文件）
    - **mood**: 情绪（可选，默认使用角色的默认情绪或normal）
    - **text_language**: 合成文本的语言（可选，默认使用配置文件）
    - **how_to_cut**: 文本切分方式（可选，默认使用配置文件）
    - **token**: WebSocket推送token，如果提供则通过WebSocket推送音频
    """
    try:
        # 检查模型是否已加载
        if not model_loaded:
            raise HTTPException(status_code=503, detail="模型尚未加载，请先切换模型或重启服务")

        # 从配置文件读取推理参数
        inference_config = config.get("inference", {})
        
        # 从全局配置中获取角色配置
        from app.config.default import DEFAULT_CONFIG
        global_config = DEFAULT_CONFIG
        characters_config = global_config.get("characters", {})

        # 获取默认角色和情绪
        default_character = character or inference_config.get("default_character", "march7")
        character_config = characters_config.get(default_character, {})

        if not character_config:
            # 如果找不到指定角色，使用第一个可用角色
            if characters_config:
                default_character = list(characters_config.keys())[0]
                character_config = characters_config[default_character]
            else:
                raise HTTPException(status_code=404, detail="未找到任何角色配置")

        # 获取情绪配置
        default_mood = mood or character_config.get("default_mood", "normal")
        moods_config = character_config.get("moods", {})
        mood_config = moods_config.get(default_mood)

        if not mood_config:
            # 如果找不到指定情绪，尝试使用normal
            mood_config = moods_config.get("normal")
            if not mood_config and moods_config:
                # 如果连normal都没有，使用第一个可用情绪
                mood_config = list(moods_config.values())[0]
            if not mood_config:
                raise HTTPException(status_code=404, detail=f"角色 {default_character} 未找到情绪配置")

        # 获取参考音频路径和文本
        ref_audio_path = mood_config.get("audio_path")
        prompt_text = mood_config.get("prompt_text", "")
        prompt_language_en = mood_config.get("language", "chinese")
        prompt_language = map_language_param(prompt_language_en)

        if not ref_audio_path or not os.path.exists(ref_audio_path):
            raise HTTPException(status_code=404, detail=f"参考音频文件不存在: {ref_audio_path}")

        # 其他参数从配置文件读取并映射
        text_language_en = text_language or inference_config.get("default_language", "chinese")
        text_language = map_language_param(text_language_en)

        how_to_cut_en = how_to_cut or inference_config.get("default_how_to_cut", "no_cut")
        how_to_cut = map_cut_method_param(how_to_cut_en)

        # 从配置文件读取固定参数
        top_k = inference_config.get("default_top_k", 15)
        top_p = inference_config.get("default_top_p", 1.0)
        temperature = inference_config.get("default_temperature", 1.0)
        ref_free = inference_config.get("default_ref_free", False)
        speed = inference_config.get("default_speed", 1.0)
        if_freeze = inference_config.get("default_if_freeze", False)
        sample_steps = inference_config.get("default_sample_steps", 8)
        if_sr = inference_config.get("default_if_sr", False)
        pause_second = inference_config.get("default_pause_second", 0.3)

        logger.info(f"使用角色: {default_character}, 情绪: {default_mood}, 参考音频: {ref_audio_path}")

        # 调用我们的 TTS 函数
        result_generator = get_tts_wav(
            ref_wav_path=ref_audio_path,
            prompt_text=prompt_text,
            prompt_language=prompt_language,
            text=text,
            text_language=text_language,
            how_to_cut=how_to_cut,
            top_k=top_k,
            top_p=top_p,
            temperature=temperature,
            ref_free=ref_free,
            speed=speed,
            if_freeze=if_freeze,
            inp_refs=None,  # 简化版本，不支持多个参考音频
            sample_steps=sample_steps,
            if_sr=if_sr,
            pause_second=pause_second,
        )

        # 获取生成的音频
        sr, audio_data = next(result_generator)

        if sr is None or audio_data is None:
            raise HTTPException(status_code=500, detail="音频生成失败")

        # 将音频数据转换为 Base64 (OGG)
        buffer = io.BytesIO()
        if isinstance(audio_data, np.ndarray):
            audio_tensor = torch.from_numpy(audio_data.astype(np.float32)) / 32767.0
        else:
            audio_tensor = audio_data
        torchaudio.save(buffer, audio_tensor.unsqueeze(0), sr, format="ogg", encoding="vorbis")
        buffer.seek(0)
        # 编码为 Base64
        audio_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        # 如果提供了token，则通过WebSocket推送音频
        if token and token.strip():
            try:
                # 构建音频数据包
                audio_packet = {
                    "type": "audio",
                    "timestamp": int(time.time() * 1000),  # 毫秒时间戳
                    "audio_base64": audio_base64,
                    "sample_rate": sr,
                    "character": default_character,
                    "mood": default_mood,
                    "text": text,
                    "message": "音频生成成功",
                    "audio_format": "ogg"
                }
                # 通过WebSocket推送音频
                await websocket_manager.send_audio_to_token(token, audio_packet)
                return {
                    "message": "音频已通过WebSocket推送",
                    "token": token,
                    "timestamp": audio_packet["timestamp"],
                    "character": default_character,
                    "mood": default_mood
                }
            except Exception as e:
                logger.error(f"WebSocket推送失败: {str(e)}")
                # 如果WebSocket推送失败，继续执行正常的返回逻辑
        return {
            "audio_base64": audio_base64,
            "sample_rate": sr,
            "character": default_character,
            "mood": default_mood,
            "audio_format": "ogg",
            "message": "合成成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS 合成失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"TTS 合成失败: {str(e)}")

# WebSocket端点
@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    WebSocket端点，用于接收音频流

    - **token**: 客户端token，用于标识不同的客户端
    """
    await websocket_manager.connect(websocket, token)
    try:
        while True:
            # 等待客户端消息（心跳包等）
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, token)
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        websocket_manager.disconnect(websocket, token)

@router.get("/characters", summary="获取角色和情绪列表")
async def get_characters():
    """获取可用的角色和情绪列表"""
    try:
        # 从全局配置中获取角色配置
        from app.config.default import DEFAULT_CONFIG
        global_config = DEFAULT_CONFIG
        characters_config = global_config.get("characters", {})
        result = {}

        for character_name, character_data in characters_config.items():
            moods = list(character_data.get("moods", {}).keys())
            result[character_name] = {
                "name": character_data.get("name", character_name),
                "default_mood": character_data.get("default_mood", "normal"),
                "available_moods": moods
            }

        return {
            "characters": result,
            "default_character": config.get("inference", {}).get("default_character", "march7")
        }

    except Exception as e:
        logger.error(f"获取角色列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取角色列表失败: {str(e)}")

@router.get("/health", summary="健康检查")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "version": "v2"
    }