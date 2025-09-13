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
                config = json.load(f)
                logger.info(f"已从 {CONFIG_FILE} 加载配置")
                
                # 合并默认配置
                merged_config = DEFAULT_CONFIG.copy()
                merged_config.update(config)
                _config = merged_config
                return _config
                
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}，将使用默认配置")
    
    # 使用默认配置
    logger.info("使用默认配置")
    _config = DEFAULT_CONFIG.copy()
    
    # 保存默认配置到文件
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(_config, f, indent=4, ensure_ascii=False)
            logger.info(f"已保存默认配置到 {CONFIG_FILE}")
    except Exception as e:
        logger.warning(f"保存默认配置失败: {e}")
        
    return _config


def get_settings() -> Dict[str, Any]:
    """获取配置"""
    if _config is None:
        return load_config()
    return _config


def update_setting(key: str, value: Any) -> bool:
    """更新配置项"""
    config = get_settings()
    config[key] = value
    
    # 保存到文件
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            logger.info(f"已更新配置项: {key}={value}")
        return True
    except Exception as e:
        logger.warning(f"保存配置失败: {e}")
        return False
