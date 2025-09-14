"""
配置模块 - 提供系统配置
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 配置日志
logger = logging.getLogger("config")

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent

# 默认配置
DEFAULT_CONFIG = {
    # 服务器配置
    "host": "0.0.0.0",  # 监听所有网络接口
    "port": 8765,
    "require_auth": False,  # 设置为False以禁用认证要求
    "api_key": "dd91538f5918826f2bdf881e88fe9956",  # 确保与客户端一致
    
    # 语音识别配置
    "asr_model_dir": "./SenseVoiceSmall",
    "use_gpu": True,
    "use_vad": True,
    "vad_threshold": 0.3,
    "vad_min_speech_duration": 0.25,
    
    # 声纹识别配置
    "database_dir": "./database",
    "vpr_model": "damo/speech_eres2netv2_sv_zh-cn_16k-common",
    "vpr_similarity_threshold": 0.25,
    "vpr_debug": False,
    "use_cache": True,
    "cache_size": 100,
    
    # 其他设置
    "only_register_user": False,
    "identify_unregistered": True
}

# 配置文件路径
CONFIG_FILE = ROOT_DIR / "config.json"

# 全局配置对象
_config = None


def load_config() -> Dict[str, Any]:
    """加载配置"""
    global _config
    
    # 如果已加载配置，直接返回
    if _config is not None:
        return _config
        
    # 尝试从文件加载配置
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                full_config = json.load(f)
                logger.info(f"已从 {CONFIG_FILE} 加载配置")
                
                # 从主配置中提取 STT 配置
                stt_config = full_config.get("stt", {})
                
                # 合并默认配置
                merged_config = DEFAULT_CONFIG.copy()
                merged_config.update(stt_config)
                _config = merged_config
                return _config
                
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}，将使用默认配置")
    
    # 使用默认配置
    logger.info("使用默认配置")
    _config = DEFAULT_CONFIG.copy()
    
    return _config


def get_settings() -> Dict[str, Any]:
    """获取配置"""
    if _config is None:
        return load_config()
    return _config


def update_setting(key: str, value: Any) -> bool:
    """更新配置项"""
    # 加载完整的配置文件
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                full_config = json.load(f)
        except Exception as e:
            logger.warning(f"读取配置文件失败: {e}")
            return False
    else:
        full_config = {}
    
    # 确保 stt 配置部分存在
    if "stt" not in full_config:
        full_config["stt"] = {}
    
    # 更新 STT 配置
    full_config["stt"][key] = value
    
    # 保存到文件
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(full_config, f, indent=4, ensure_ascii=False)
            logger.info(f"已更新配置项: stt.{key}={value}")
        
        # 更新内存中的配置
        global _config
        if _config is not None:
            _config[key] = value
            
        return True
    except Exception as e:
        logger.warning(f"保存配置失败: {e}")
        return False
