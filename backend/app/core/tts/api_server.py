#!/usr/bin/env python3
"""
GPT-SoVITS FastAPI 服务器主入口
替代原有的 Gradio WebUI，提供 REST API 接口
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

# 导入路由模块
from router import router, set_config

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
    pretrained_models = tts_config["pretrained_models"]
    
    # 设置默认模型路径
    os.environ["GPT_PATH"] = default_models["gpt_path"]
    os.environ["SOVITS_PATH"] = default_models["sovits_path"]
    
    # 设置预训练模型路径
    os.environ["VOCODER_PATH"] = pretrained_models["vocoder_path"]
    
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

# 设置路由模块的配置
set_config(tts_config)

# 包含路由
app.include_router(router)

# 在应用启动时初始化模型
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("正在启动 GPT-SoVITS API 服务器...")
    # 模型初始化将在路由模块中处理
    logger.info("服务器启动完成")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GPT-SoVITS FastAPI Server")
    parser.add_argument("--host", default=None, help="Host to bind to")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    
    args = parser.parse_args()
    
    # 使用配置文件中的服务器设置，命令行参数优先
    server_config = tts_config["server"]
    host = args.host or server_config["host"]
    port = args.port or server_config["port"]
    log_level = server_config["log_level"]
    
    logger.info(f"启动 GPT-SoVITS FastAPI 服务器")
    logger.info(f"访问地址: http://{host}:{port}")
    logger.info(f"API 文档: http://{host}:{port}/docs")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=args.workers,
        log_level=log_level
    )
