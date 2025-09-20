#!/usr/bin/env python3
"""
GPT-SoVITS FastAPI 应用核心模块
包含应用初始化、配置加载和模型设置
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
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# 导入我们的核心推理模块
tts_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(tts_dir))))
sys.path.append(tts_dir)
sys.path.append(os.path.join(project_root, "GPT_SoVITS"))
from core_inference import (
    get_tts_wav,
    load_models,
    change_sovits_weights,
    change_gpt_weights,
    dict_language
)

# 导入后端配置模块
from app.config.default import DEFAULT_CONFIG

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 抑制警告
warnings.filterwarnings("ignore")

# 获取TTS配置
tts_config = DEFAULT_CONFIG["tts"]["gpt_sovits"]

# 设置模型路径环境变量
def set_model_env_vars():
    """设置模型路径环境变量"""
    default_models = tts_config["default_models"]
    pretrained_models = tts_config.get("pretrained_models", {})

    # 设置默认模型路径
    os.environ["GPT_PATH"] = default_models["gpt_path"]
    os.environ["SOVITS_PATH"] = default_models["sovits_path"]

    # 设置预训练模型路径
    os.environ["VOCODER_PATH"] = pretrained_models.get("vocoder_path",
                                                      f"{project_root}/GPT_SoVITS/models/gsv-v4-pretrained/vocoder.pth")

    logger.info(f"设置GPT模型路径: {os.environ['GPT_PATH']}")
    logger.info(f"设置SoVITS模型路径: {os.environ['SOVITS_PATH']}")
    logger.info(f"设置Vocoder路径: {os.environ['VOCODER_PATH']}")

# 设置环境变量
set_model_env_vars()

# 创建FastAPI应用
app = FastAPI(
    title="GPT-SoVITS API",
    description="GPT-SoVITS 语音合成 API 接口",
    version="1.0.0"
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 在应用启动时初始化模型
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("正在启动 GPT-SoVITS API 服务器...")
    # 模型初始化将在路由模块中处理
    logger.info("服务器启动完成")