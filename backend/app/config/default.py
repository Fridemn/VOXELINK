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
        "context_window": get_config_value("llm.context_window", int, 10),
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

# GPT-SoVITS TTS配置
DEFAULT_CONFIG["tts"] = {
    "gpt_sovits": {
        "default_models": {
            "sovits_path": get_config_value("default_models.sovits_path", str, "backend/GPT_SoVITS/models/SoVITS_weights_v4/March7_e10_s4750_l32.pth"),
            "gpt_path": get_config_value("default_models.gpt_path", str, "backend/GPT_SoVITS/models/GPT_weights_v4/March7-e15.ckpt")
        },
        "pretrained_models": {
            "vocoder_path": get_config_value("pretrained_models.vocoder_path", str, "backend/GPT_SoVITS/models/gsv-v4-pretrained/vocoder.pth"),
            "sovits_v1": get_config_value("pretrained_models.sovits_v1", str, "backend/GPT_SoVITS/models/s2G488k.pth"),
            "sovits_v2": get_config_value("pretrained_models.sovits_v2", str, "backend/GPT_SoVITS/models/gsv-v2final-pretrained/s2G2333k.pth"),
            "sovits_v3": get_config_value("pretrained_models.sovits_v3", str, "backend/GPT_SoVITS/models/s2Gv3.pth"),
            "sovits_v4": get_config_value("pretrained_models.sovits_v4", str, "backend/GPT_SoVITS/models/gsv-v4-pretrained/s2Gv4.pth"),
            "gpt_v1": get_config_value("pretrained_models.gpt_v1", str, "backend/GPT_SoVITS/models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt"),
            "gpt_v2": get_config_value("pretrained_models.gpt_v2", str, "backend/GPT_SoVITS/models/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"),
            "gpt_v3": get_config_value("pretrained_models.gpt_v3", str, "backend/GPT_SoVITS/models/s1v3.ckpt"),
            "gpt_v4": get_config_value("pretrained_models.gpt_v4", str, "backend/GPT_SoVITS/models/s1v3.ckpt")
        },
        "server": {
            "host": get_config_value("server.host", str, "0.0.0.0"),
            "port": get_config_value("server.port", int, 9880),
            "log_level": get_config_value("server.log_level", str, "info")
        },
        "inference": {
            "default_character": get_config_value("inference.default_character", str, "march7"),
            "default_mood": get_config_value("inference.default_mood", str, "normal"),
            "default_language": get_config_value("inference.default_language", str, "chinese"),
            "default_how_to_cut": get_config_value("inference.default_how_to_cut", str, "no_cut"),
            "default_top_k": get_config_value("inference.default_top_k", int, 15),
            "default_top_p": get_config_value("inference.default_top_p", float, 1.0),
            "default_temperature": get_config_value("inference.default_temperature", float, 1.0),
            "default_ref_free": get_config_value("inference.default_ref_free", bool, False),
            "default_speed": get_config_value("inference.default_speed", float, 1.0),
            "default_if_freeze": get_config_value("inference.default_if_freeze", bool, False),
            "default_sample_steps": get_config_value("inference.default_sample_steps", int, 8),
            "default_if_sr": get_config_value("inference.default_if_sr", bool, False),
            "default_pause_second": get_config_value("inference.default_pause_second", float, 0.3)
        }
    }
}

# 角色配置
DEFAULT_CONFIG["characters"] = {
    "march7": {
        "name": "三月七",
        "default_mood": "normal",
        "moods": {
            "normal": {
                "audio_path": "backend/GPT_SoVITS/ref_audio/march7/nomal.wav",
                "prompt_text": "裂界，确实会对周围空间造成很多影响啦。空间站电子设备这么多，是不是经常发生短路？",
                "language": "chinese"
            },
            "excited": {
                "audio_path": "backend/GPT_SoVITS/ref_audio/march7/excited.wav",
                "prompt_text": "哇！太棒了！我超级兴奋！",
                "language": "chinese"
            },
            "confused": {
                "audio_path": "backend/GPT_SoVITS/ref_audio/march7/confused.wav",
                "prompt_text": "诶？这是什么情况？我有点困惑。",
                "language": "chinese"
            }
        }
    }
}

# VAD配置 (fsmn-vad参数)
DEFAULT_CONFIG["vad"] = {
    "threshold": get_config_value("vad.threshold", float, 0.3),  # VAD阈值 - 降低阈值以提高检测灵敏度
    "min_speech_duration_ms": get_config_value("vad.min_speech_duration_ms", int, 100),  # 最短语音持续时间 - 降低以检测短语音
    "max_speech_duration_s": get_config_value("vad.max_speech_duration_s", float, 30),  # 最长语音持续时间
    "min_silence_duration_ms": get_config_value("vad.min_silence_duration_ms", int, 300),  # 最短静音持续时间 - 降低以更快响应
    "window_size_samples": get_config_value("vad.window_size_samples", int, 1024),  # 窗口大小
    "speech_pad_ms": get_config_value("vad.speech_pad_ms", int, 30),  # 语音填充时间
    "min_chunk_speech_duration": get_config_value("vad.min_chunk_speech_duration", float, 0.05),  # 音频块最少语音时长 - 降低以检测更短的语音
}

# GUI配置
DEFAULT_CONFIG["gui"] = {
    "models": {
        "llm_models": get_config_value("gui.models.llm_models", list, ["deepseek/deepseek-v3-0324", "gpt-3.5-turbo", "gpt-4"]),
        "default_llm_model": get_config_value("gui.models.default_llm_model", str, "deepseek/deepseek-v3-0324")
    },
    "realtime_chat": {
        "stream": get_config_value("gui.realtime_chat.stream", bool, True),
        "tts": get_config_value("gui.realtime_chat.tts", bool, True)
    },
    "server": {
        "default_host": get_config_value("gui.server.default_host", str, "0.0.0.0"),
        "default_port": get_config_value("gui.server.default_port", int, 8080),
        "stt_ws_url": get_config_value("gui.server.stt_ws_url", str, "ws://localhost:8080/stt/ws"),
        "realtime_chat_ws_url": get_config_value("gui.server.realtime_chat_ws_url", str, "ws://localhost:8080/ws/realtime_chat")
    },
    "vad": {
        "stt": {
            "sample_rate": get_config_value("gui.vad.stt.sample_rate", int, 16000),
            "channels": get_config_value("gui.vad.stt.channels", int, 1),
            "chunk_size": get_config_value("gui.vad.stt.chunk_size", int, 2048),
            "vad_threshold": get_config_value("gui.vad.stt.vad_threshold", float, 0.15),
            "min_speech_frames": get_config_value("gui.vad.stt.min_speech_frames", int, 2),
            "max_silence_frames": get_config_value("gui.vad.stt.max_silence_frames", int, 5),
            "audio_rms_threshold": get_config_value("gui.vad.stt.audio_rms_threshold", float, 0.025),
            "real_time_frames": get_config_value("gui.vad.stt.real_time_frames", int, 15),
            "tail_threshold_ratio": get_config_value("gui.vad.stt.tail_threshold_ratio", float, 0.4),
            "speech_padding_frames": get_config_value("gui.vad.stt.speech_padding_frames", int, 2),
            "end_speech_delay_ms": get_config_value("gui.vad.stt.end_speech_delay_ms", int, 300)
        },
        "realtime_chat": {
            "sample_rate": get_config_value("gui.vad.realtime_chat.sample_rate", int, 16000),
            "channels": get_config_value("gui.vad.realtime_chat.channels", int, 1),
            "chunk_size": get_config_value("gui.vad.realtime_chat.chunk_size", int, 2048),
            "vad_threshold": get_config_value("gui.vad.realtime_chat.vad_threshold", float, 0.15),
            "min_speech_frames": get_config_value("gui.vad.realtime_chat.min_speech_frames", int, 2),
            "max_silence_frames": get_config_value("gui.vad.realtime_chat.max_silence_frames", int, 8),
            "audio_rms_threshold": get_config_value("gui.vad.realtime_chat.audio_rms_threshold", float, 0.025)
        }
    }
}
