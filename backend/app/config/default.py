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
    "llm": {
        "default_model": get_config_value("llm.default_model", str, "gpt-3.5-turbo"),
        "openai_models": get_config_value("llm.openai_models", list, ["gpt-3.5-turbo", "gpt-4"]),
        "ollama_base_url": get_config_value("llm.ollama_base_url", str, "http://localhost:11434"),
        "ollama_models": get_config_value("llm.ollama_models", list, ["llama2"]),
        "context_window": get_config_value("llm.context_window", int, 10),
    },
    "database": {
        "engine": get_config_value("database.engine", str, "sqlite"),
        "use_tz": get_config_value("database.use_tz", bool, True),
        "time_zone": get_config_value("database.time_zone", str, "Asia/Shanghai"),
    },
}

DEFAULT_CONFIG["stt"] = {
    "sensevoice": {
        "model_dir": get_config_value("stt.sensevoice.model_dir", str, "./SenseVoiceSmall"),
        "language": get_config_value("stt.sensevoice.language", str, "zh"),
        "use_gpu": get_config_value("stt.sensevoice.use_gpu", bool, True),
        "use_vad": get_config_value("stt.sensevoice.use_vad", bool, True),
        "vad_threshold": get_config_value("stt.sensevoice.vad_threshold", float, 0.3),
        "vad_min_speech_duration": get_config_value("stt.sensevoice.vad_min_speech_duration", float, 0.25)
    },
    "host": get_config_value("stt.host", str, "0.0.0.0"),
    "port": get_config_value("stt.port", int, 8765),
    "require_auth": get_config_value("stt.require_auth", bool, False),
    "database_dir": get_config_value("stt.database_dir", str, "./database"),
    "vpr_model": get_config_value("stt.vpr_model", str, "damo/speech_eres2netv2_sv_zh-cn_16k-common"),
    "vpr_similarity_threshold": get_config_value("stt.vpr_similarity_threshold", float, 0.25),
    "vpr_debug": get_config_value("stt.vpr_debug", bool, False),
    "use_cache": get_config_value("stt.use_cache", bool, True),
    "cache_size": get_config_value("stt.cache_size", int, 100),
    "only_register_user": get_config_value("stt.only_register_user", bool, False),
    "identify_unregistered": get_config_value("stt.identify_unregistered", bool, True)
}

# TTS服务配置
DEFAULT_CONFIG["tts_config"] = {
    "base_url": get_config_value("tts_config.base_url", str, "http://localhost:9880"),  # TTS服务的基础URL
    "default_character": get_config_value("tts_config.default_character", str, "march7"),
    "default_mood": get_config_value("tts_config.default_mood", str, "normal"),
    "default_models": {
        "sovits_path": get_config_value("tts_config.default_models.sovits_path", str, "GPT_SoVITS/models/SoVITS_weights_v4/March7_e10_s4750_l32.pth"),
        "gpt_path": get_config_value("tts_config.default_models.gpt_path", str, "GPT_SoVITS/models/GPT_weights_v4/March7-e15.ckpt")
    },
    "default_language": get_config_value("tts_config.default_language", str, "chinese"),
    "default_how_to_cut": get_config_value("tts_config.default_how_to_cut", str, "no_cut"),
    "default_top_k": get_config_value("tts_config.default_top_k", int, 15),
    "default_top_p": get_config_value("tts_config.default_top_p", float, 1.0),
    "default_temperature": get_config_value("tts_config.default_temperature", float, 1.0),
    "default_ref_free": get_config_value("tts_config.default_ref_free", bool, False),
    "default_speed": get_config_value("tts_config.default_speed", float, 1.0),
    "default_if_freeze": get_config_value("tts_config.default_if_freeze", bool, False),
    "default_sample_steps": get_config_value("tts_config.default_sample_steps", int, 8),
    "default_if_sr": get_config_value("tts_config.default_if_sr", bool, False),
    "default_pause_second": get_config_value("tts_config.default_pause_second", float, 0.3),
    "pretrained_models": {
        "vocoder_path": get_config_value("tts_config.pretrained_models.vocoder_path", str, "backend/GPT_SoVITS/models/gsv-v4-pretrained/vocoder.pth"),
        "sovits_v1": get_config_value("tts_config.pretrained_models.sovits_v1", str, "backend/GPT_SoVITS/models/s2G488k.pth"),
        "sovits_v2": get_config_value("tts_config.pretrained_models.sovits_v2", str, "backend/GPT_SoVITS/models/gsv-v2final-pretrained/s2G2333k.pth"),
        "sovits_v3": get_config_value("tts_config.pretrained_models.sovits_v3", str, "backend/GPT_SoVITS/models/s2Gv3.pth"),
        "sovits_v4": get_config_value("tts_config.pretrained_models.sovits_v4", str, "backend/GPT_SoVITS/models/gsv-v4-pretrained/s2Gv4.pth"),
        "gpt_v1": get_config_value("tts_config.pretrained_models.gpt_v1", str, "backend/GPT_SoVITS/models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt"),
        "gpt_v2": get_config_value("tts_config.pretrained_models.gpt_v2", str, "backend/GPT_SoVITS/models/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"),
        "gpt_v3": get_config_value("tts_config.pretrained_models.gpt_v3", str, "backend/GPT_SoVITS/models/s1v3.ckpt"),
        "gpt_v4": get_config_value("tts_config.pretrained_models.gpt_v4", str, "backend/GPT_SoVITS/models/s1v3.ckpt")
    },
    "server": {
        "host": get_config_value("tts_config.server.host", str, "0.0.0.0"),
        "port": get_config_value("tts_config.server.port", int, 9880),
        "log_level": get_config_value("tts_config.server.log_level", str, "info")
    },
    "characters": {
        "march7": {
            "name": get_config_value("tts_config.characters.march7.name", str, "三月七"),
            "default_mood": get_config_value("tts_config.characters.march7.default_mood", str, "normal"),
            "moods": {
                "normal": {
                    "audio_path": get_config_value("tts_config.characters.march7.moods.normal.audio_path", str, "backend/GPT_SoVITS/ref_audio/march7/nomal.wav"),
                    "prompt_text": get_config_value("tts_config.characters.march7.moods.normal.prompt_text", str, "裂界，确实会对周围空间造成很多影响啦。空间站电子设备这么多，是不是经常发生短路？"),
                    "language": get_config_value("tts_config.characters.march7.moods.normal.language", str, "chinese")
                },
                "excited": {
                    "audio_path": get_config_value("tts_config.characters.march7.moods.excited.audio_path", str, "backend/GPT_SoVITS/ref_audio/march7/excited.wav"),
                    "prompt_text": get_config_value("tts_config.characters.march7.moods.excited.prompt_text", str, "哇！太棒了！我超级兴奋！"),
                    "language": get_config_value("tts_config.characters.march7.moods.excited.language", str, "chinese")
                },
                "confused": {
                    "audio_path": get_config_value("tts_config.characters.march7.moods.confused.audio_path", str, "backend/GPT_SoVITS/ref_audio/march7/confused.wav"),
                    "prompt_text": get_config_value("tts_config.characters.march7.moods.confused.prompt_text", str, "诶？这是什么情况？我有点困惑。"),
                    "language": get_config_value("tts_config.characters.march7.moods.confused.language", str, "chinese")
                }
            }
        }
    },
    "inference": {
        "default_character": get_config_value("tts_config.inference.default_character", str, "march7"),
        "default_mood": get_config_value("tts_config.inference.default_mood", str, "normal"),
        "default_language": get_config_value("tts_config.inference.default_language", str, "chinese"),
        "default_how_to_cut": get_config_value("tts_config.inference.default_how_to_cut", str, "no_cut"),
        "default_top_k": get_config_value("tts_config.inference.default_top_k", int, 15),
        "default_top_p": get_config_value("tts_config.inference.default_top_p", float, 1.0),
        "default_temperature": get_config_value("tts_config.inference.default_temperature", float, 1.0),
        "default_ref_free": get_config_value("tts_config.inference.default_ref_free", bool, False),
        "default_speed": get_config_value("tts_config.inference.default_speed", float, 1.0),
        "default_if_freeze": get_config_value("tts_config.inference.default_if_freeze", bool, False),
        "default_sample_steps": get_config_value("tts_config.inference.default_sample_steps", int, 8),
        "default_if_sr": get_config_value("tts_config.inference.default_if_sr", bool, False),
        "default_pause_second": get_config_value("tts_config.inference.default_pause_second", float, 0.3)
    }
}

# VAD配置 (fsmn-vad参数)
DEFAULT_CONFIG["vad"] = {
    "threshold": get_config_value("stt.sensevoice.vad_threshold", float, 0.3),  # VAD阈值
    "min_speech_duration_ms": int(get_config_value("stt.sensevoice.vad_min_speech_duration", float, 0.25) * 1000),  # 最短语音持续时间 (毫秒)
    "max_speech_duration_s": get_config_value("vad.max_speech_duration_s", float, 30),  # 最长语音持续时间
    "min_silence_duration_ms": get_config_value("vad.min_silence_duration_ms", int, 300),  # 最短静音持续时间
    "window_size_samples": get_config_value("vad.window_size_samples", int, 1024),  # 窗口大小
    "speech_pad_ms": get_config_value("vad.speech_pad_ms", int, 30),  # 语音填充时间
    "merge_vad": get_config_value("vad.merge_vad", bool, True),  # 是否合并VAD分割的短音频片段
    "merge_length_s": get_config_value("vad.merge_length_s", int, 15),  # 合并长度（秒）
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
    }
}

# Live2D配置
DEFAULT_CONFIG["live2d"] = {
    "model_name": get_config_value("live2d.model_name", str, "march7"),
    "model_display_name": get_config_value("live2d.model_display_name", str, "三月七 (March 7th)"),
    "model_dir": get_config_value("live2d.model_dir", str, "march7"),
    "models": {
        "march7": {
            "name": "三月七",
            "model_file": "三月七.model3.json",
            "directory": "march7"
        }
    }
}
