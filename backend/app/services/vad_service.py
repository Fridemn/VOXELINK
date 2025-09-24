"""
语音活动检测服务 - 基于fsmn-vad实现
"""

import logging
import numpy as np
import torch
import tempfile
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent


def get_vad_settings() -> Dict[str, Any]:
    """获取VAD配置"""
    # 使用后端统一配置系统
    try:
        from app.config.default import DEFAULT_CONFIG
        return DEFAULT_CONFIG.get("vad", {})
    except Exception as e:
        logger.warning(f"无法加载后端配置，使用空配置: {e}")
        return {}


# 配置日志
logger = logging.getLogger("vad_service")


class VADService:
    """语音活动检测服务类 - 基于fsmn-vad"""

    def __init__(self):
        """初始化VAD服务"""
        self.settings = get_vad_settings()
        self.model = None
        self.vad_model = None
        self.get_speech_timestamps = None

        # 初始化fsmn-vad模型
        self._init_vad_model()

    def _init_vad_model(self):
        """初始化fsmn-vad模型"""
        try:
            # 导入torch.hub加载fsmn-vad
            logger.info("正在加载fsmn-vad模型...")
            self.vad_model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            self.get_speech_timestamps = utils[0]
            logger.info("fsmn-vad模型加载完成")

        except Exception as e:
            logger.error(f"初始化fsmn-vad模型失败: {str(e)}", exc_info=True)
            self.vad_model = None

    def detect_speech(self, audio_data: bytes, sample_rate: int = 16000) -> Dict[str, Any]:
        """检测音频中的语音活动

        Args:
            audio_data: 音频数据（PCM格式）
            sample_rate: 采样率

        Returns:
            检测结果，包含语音时间戳
        """
        if self.vad_model is None or self.get_speech_timestamps is None:
            return {"success": False, "error": "VAD模型未初始化"}

        if len(audio_data) == 0:
            logger.warning("接收到空的音频数据")
            return {"success": False, "error": "音频数据为空"}

        try:
            # 将字节数据转换为numpy数组
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            # 检查音频数据是否有效
            if np.all(audio_np == 0):
                logger.debug("音频数据全为静音")
                return {
                    "success": True,
                    "speech_detected": False,
                    "speech_segments": [],
                    "total_speech_duration": 0.0
                }

            logger.debug(f"音频数据统计: 长度={len(audio_np)}, 均值={np.mean(np.abs(audio_np)):.4f}, "
                        f"最大值={np.max(np.abs(audio_np)):.4f}")

            # 获取VAD参数
            threshold = self.settings.get("threshold", 0.3)
            min_speech_duration_ms = self.settings.get("min_speech_duration_ms", 100)
            max_speech_duration_s = self.settings.get("max_speech_duration_s", 30)
            min_silence_duration_ms = self.settings.get("min_silence_duration_ms", 300)
            window_size_samples = self.settings.get("window_size_samples", 1024)
            speech_pad_ms = self.settings.get("speech_pad_ms", 30)

            logger.debug(f"VAD参数: threshold={threshold}, min_speech={min_speech_duration_ms}ms, "
                        f"min_silence={min_silence_duration_ms}ms")

            # 执行语音活动检测
            speech_timestamps = self.get_speech_timestamps(
                audio_np,
                self.vad_model,
                threshold=threshold,
                sampling_rate=sample_rate,
                min_speech_duration_ms=min_speech_duration_ms,
                max_speech_duration_s=max_speech_duration_s,
                min_silence_duration_ms=min_silence_duration_ms,
                window_size_samples=window_size_samples,
                speech_pad_ms=speech_pad_ms
            )

            # 转换为更易用的格式
            speech_segments = []
            for timestamp in speech_timestamps:
                speech_segments.append({
                    "start": timestamp["start"],
                    "end": timestamp["end"],
                    "duration": timestamp["end"] - timestamp["start"]
                })

            return {
                "success": True,
                "speech_detected": len(speech_segments) > 0,
                "speech_segments": speech_segments,
                "total_speech_duration": sum(seg["duration"] for seg in speech_segments)
            }

        except Exception as e:
            logger.error(f"VAD检测失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"VAD检测失败: {str(e)}"
            }

    def detect_speech_segments(self, audio_data: bytes, sample_rate: int = 16000) -> Dict[str, Any]:
        """检测音频中的语音活动段落

        Args:
            audio_data: 音频数据（PCM格式）
            sample_rate: 采样率

        Returns:
            检测结果，包含语音段落信息
        """
        result = self.detect_speech(audio_data, sample_rate)
        if not result["success"]:
            return result

        # 计算音频块时长和RMS（用于前端显示）
        chunk_duration = len(audio_data) / (sample_rate * 2) if len(audio_data) > 0 else 0
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio_np ** 2))) if len(audio_np) > 0 else 0.0

        # 计算语音比例作为置信度
        speech_ratio = result["total_speech_duration"] / chunk_duration if chunk_duration > 0 else 0

        return {
            "success": True,
            "speech_detected": result["speech_detected"],
            "speech_segments": result["speech_segments"],
            "total_speech_duration": result["total_speech_duration"],
            "confidence": speech_ratio,
            "rms": rms,
            "chunk_duration": chunk_duration
        }


# 全局单例
_vad_service = None


def get_vad_service() -> VADService:
    """获取VAD服务实例

    Returns:
        VAD服务实例
    """
    global _vad_service
    if _vad_service is None:
        _vad_service = VADService()
    return _vad_service