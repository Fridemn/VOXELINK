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
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core_inference import (
    get_tts_wav,
    load_models,
    change_sovits_weights,
    change_gpt_weights,
    dict_language
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 抑制警告
warnings.filterwarnings("ignore")

# 加载配置文件
def load_config():
    """加载配置文件"""
    config_path = "config.json"
    default_config = {
        "default_models": {
            "sovits_path": "/home/fridemn/projects/GPT-SoVITS/SoVITS_weights_v4/March7_e10_s4750_l32.pth",
            "gpt_path": "/home/fridemn/projects/GPT-SoVITS/GPT_weights_v4/March7-e15.ckpt"
        },
        "server": {
            "host": "0.0.0.0",
            "port": 9880,
            "log_level": "info"
        },
        "inference": {
            "default_language": "chinese",
            "default_how_to_cut": "no_cut",
            "default_top_k": 15,
            "default_top_p": 1.0,
            "default_temperature": 1.0,
            "default_ref_free": False,
            "default_speed": 1.0,
            "default_if_freeze": False,
            "default_sample_steps": 8,
            "default_if_sr": False,
            "default_pause_second": 0.3
        }
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"配置文件加载成功: {config_path}")
            return config
        except Exception as e:
            logger.warning(f"配置文件加载失败，使用默认配置: {e}")
            return default_config
    else:
        # 创建默认配置文件
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            logger.info(f"创建默认配置文件: {config_path}")
        except Exception as e:
            logger.warning(f"无法创建配置文件: {e}")
        return default_config

# 加载配置
config = load_config()

# 设置模型路径环境变量
def set_model_env_vars():
    """设置模型路径环境变量"""
    default_models = config.get("default_models", {})
    pretrained_models = config.get("pretrained_models", {})

    # 设置默认模型路径
    os.environ["GPT_PATH"] = default_models.get("gpt_path", "GPT_weights_v4/March7-e15.ckpt")
    os.environ["SOVITS_PATH"] = default_models.get("sovits_path", "SoVITS_weights_v4/March7_e10_s4750_l32.pth")

    # 设置预训练模型路径
    os.environ["VOCODER_PATH"] = pretrained_models.get("vocoder_path",
                                                      f"{os.getcwd()}/GPT_SoVITS/pretrained_models/gsv-v4-pretrained/vocoder.pth")

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