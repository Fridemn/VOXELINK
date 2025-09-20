"""
app/config/default.py
默认配置内容。
- 存储各类默认配置字典。
- 从 config.json 文件读取配置，支持类型转换和参数化配置。
"""

import os
import sys
import json
from typing import Optional, TypeVar, Type
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent

_T = TypeVar("_T")


def get_config_value(key_path: str, type_: Type[_T], default: Optional[_T] = None) -> _T:
    """从 config.json 获取指定的配置值，并自动转换为指定的类型"""
    config_file = ROOT_DIR / "config.json"
    
    try:
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}
    except Exception as e:
        print(f"❌ Error: Failed to load config.json: {e}")
        config = {}
    
    # 解析 key_path，如 "openai.api_key"
    keys = key_path.split(".")
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            value = None
            break
    
    if value is None:
        if default is None:
            print(f"❌ Error: Required config key '{key_path}' (type={type_}) not found.")
            print(f"👉 Please setup '{key_path}' in your 'config.json' file.")
            sys.exit(1)
        return default

    if type_ == str:
        result = value
    elif type_ == int:
        result = int(value)
    elif type_ == float:
        result = float(value)
    elif type_ == bool:
        result = bool(value)
    elif type_ == list:
        result = value if isinstance(value, list) else [value]
    else:
        raise TypeError(f"Unsupported conversion type: {type_}")

    assert isinstance(result, type_)
    return result


# 配置字典
DEFAULT_CONFIG = {
    "openai": {
        "api_key": get_config_value("openai.api_key", str, "sk-default-key"),
        "base_url": get_config_value("openai.base_url", str, "https://api.openai.com/v1"),
    },
    "anthropic": {
        "api_key": get_config_value("anthropic.api_key", str, "sk-ant-default-key"),
    },
    "custom_endpoint": {
        "api_key": get_config_value("custom_endpoint.api_key", str, "default-custom-key"),
    },
    "stt": {
        "active_service": get_config_value("stt.active_service", str, "openai"),
        "openai_model": get_config_value("stt.openai_model", str, "whisper-1"),
    },
    "tts": {
        "active_service": get_config_value("tts.active_service", str, "edge"),
        "edge_voice": get_config_value("tts.edge_voice", str, "zh-CN-XiaoxiaoNeural"),
    },
    "llm": {
        "default_model": get_config_value("llm.default_model", str, "gpt-3.5-turbo"),
        "openai_models": get_config_value("llm.openai_models", list, ["gpt-3.5-turbo", "gpt-4"]),
        "anthropic_models": get_config_value("llm.anthropic_models", list, ["claude-3-7-sonnet"]),
        "ollama_base_url": get_config_value("llm.ollama_base_url", str, "http://localhost:11434"),
        "ollama_models": get_config_value("llm.ollama_models", list, ["llama2"]),
        "custom_endpoint_base_url": get_config_value("llm.custom_endpoint_base_url", str, "http://your-custom-endpoint"),
        "custom_endpoint_models": get_config_value("llm.custom_endpoint_models", list, ["custom-model-1"]),
    },
    "database": {
        "engine": get_config_value("database.engine", str, "sqlite"),
        "use_tz": get_config_value("database.use_tz", bool, True),
        "time_zone": get_config_value("database.time_zone", str, "Asia/Shanghai"),
    },
    "jwt": {
        "secret_key": get_config_value("jwt.secret_key", str, "your-secret-key-here"),
        "algorithm": get_config_value("jwt.algorithm", str, "HS256"),
        "access_token_expire_minutes": get_config_value("jwt.access_token_expire_minutes", int, 30),
    },
}

# TTS服务配置
DEFAULT_CONFIG["tts_config"] = {
    "base_url": get_config_value("tts_config.base_url", str, "http://localhost:9880"),  # TTS服务的基础URL
    "default_character": get_config_value("tts_config.default_character", str, "march7"),
    "default_mood": get_config_value("tts_config.default_mood", str, "normal"),
}
