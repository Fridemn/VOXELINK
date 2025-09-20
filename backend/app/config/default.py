"""
app/config/default.py
默认配置内容。
- 存储各类默认配置字典。
- 使用 TypeVar 重构环境变量读取，支持类型转换和参数化配置。
"""

import os
import sys
from typing import Optional, TypeVar, Type
from dotenv import load_dotenv
from .constant import *

load_dotenv(override=True)

_T = TypeVar("_T")


def get_env(key: str, type_: Type[_T], default: Optional[_T] = None) -> _T:
    """获取指定的环境变量，并自动转换为指定的类型。若 default 为 None，则表示该环境变量为必需项"""
    value = os.getenv(key)

    if value is None:
        if default is None:
            print(f"❌ Error: Required env variable '{key}' (type={type_}) not found.")
            print(f"👉 Please setup '{key}' in your '.env' file.")
            sys.exit(1)
        return default

    if type_ == str:
        result = value
    elif type_ == int:
        result = int(value)
    elif type_ == float:
        result = float(value)
    elif type_ == bool:
        result = value.lower() in ("true", "1", "yes", "on")
    elif type_ == list:
        result = value.split(",") if value else []
    else:
        raise TypeError(f"Unsupported conversion type: {type_}")

    assert isinstance(result, type_)
    return result


# 配置字典
DEFAULT_CONFIG = {
    "openai": {
        "api_key": get_env("OPENAI_API_KEY", str, "sk-default-key"),
        "base_url": get_env("OPENAI_BASE_URL", str, "https://api.openai.com/v1"),
    },
    "anthropic": {
        "api_key": get_env("ANTHROPIC_API_KEY", str, "sk-ant-default-key"),
    },
    "custom_endpoint": {
        "api_key": get_env("CUSTOM_ENDPOINT_API_KEY", str, "default-custom-key"),
    },
    "stt": {
        "active_service": get_env("STT_ACTIVE_SERVICE", str, "openai"),
        "openai_model": get_env("STT_OPENAI_MODEL", str, "whisper-1"),
    },
    "tts": {
        "active_service": get_env("TTS_ACTIVE_SERVICE", str, "edge"),
        "edge_voice": get_env("TTS_EDGE_VOICE", str, "zh-CN-XiaoxiaoNeural"),
    },
    "llm": {
        "default_model": get_env("LLM_DEFAULT_MODEL", str, "gpt-3.5-turbo"),
        "openai_models": get_env("LLM_OPENAI_MODELS", list, ["gpt-3.5-turbo", "gpt-4"]),
        "anthropic_models": get_env("LLM_ANTHROPIC_MODELS", list, ["claude-3-7-sonnet"]),
        "ollama_base_url": get_env("LLM_OLLAMA_BASE_URL", str, "http://localhost:11434"),
        "ollama_models": get_env("LLM_OLLAMA_MODELS", list, ["llama2"]),
        "custom_endpoint_base_url": get_env("LLM_CUSTOM_ENDPOINT_BASE_URL", str, "http://your-custom-endpoint"),
        "custom_endpoint_models": get_env("LLM_CUSTOM_ENDPOINT_MODELS", list, ["custom-model-1"]),
    },
    "database": {
        "engine": get_env("DB_ENGINE", str, "sqlite"),
        "use_tz": get_env("DB_USE_TZ", bool, True),
        "time_zone": get_env("DB_TIME_ZONE", str, "Asia/Shanghai"),
    },
    "jwt": {
        "secret_key": get_env("JWT_SECRET_KEY", str, "your-secret-key-here"),
        "algorithm": get_env("JWT_ALGORITHM", str, "HS256"),
        "access_token_expire_minutes": get_env("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", int, 30),
    },
}

# TTS服务配置
DEFAULT_CONFIG["tts_config"] = {
    "base_url": os.getenv("TTS_BASE_URL", "http://localhost:9880"),  # TTS服务的基础URL
    "default_character": "march7",
    "default_mood": "normal",
}
