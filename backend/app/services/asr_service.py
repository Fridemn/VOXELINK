"""
语音识别服务 - 提供语音识别功能
"""

import logging
import numpy as np
import base64
import os
import tempfile
import io
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent


def get_stt_settings() -> Dict[str, Any]:
    """获取STT配置"""
    # 使用后端统一配置系统
    try:
        from .. import app_config
        return app_config.get("stt", {})
    except Exception as e:
        logger.warning(f"无法加载后端配置，使用空配置: {e}")
        return {}


def get_vad_settings() -> Dict[str, Any]:
    """获取VAD配置"""
    try:
        from .. import app_config
        return app_config.get("vad", {})
    except Exception as e:
        logger.warning(f"无法加载VAD配置: {e}")
        return {}


# 配置日志
logger = logging.getLogger("asr_service")


class ASRService:
    """语音识别服务类"""
    
    def __init__(self):
        """初始化语音识别服务"""
        self.settings = get_stt_settings()
        self.vad_settings = get_vad_settings()
        self.model = None
        
        # 初始化ASR模型
        self._init_asr_model()
    
    def _init_asr_model(self):
        """初始化ASR模型"""
        try:
            from funasr import AutoModel

            model_dir = self.settings.get("asr_model_dir", "./SenseVoiceSmall")

            # 确保路径指向backend目录下的SenseVoiceSmall
            if model_dir.startswith("./"):
                # 获取backend目录路径
                backend_dir = Path(__file__).parent.parent.parent
                model_dir = backend_dir / model_dir[2:]  # 移除./前缀
            elif not os.path.isabs(model_dir):
                # 相对路径，相对于backend目录
                backend_dir = Path(__file__).parent.parent.parent
                model_dir = backend_dir / model_dir

            model_dir = str(model_dir)
            use_gpu = self.settings.get("use_gpu", True)

            # 检查目录是否存在
            if not os.path.exists(model_dir):
                logger.error(f"ASR模型目录不存在: {model_dir}")
                return
            # 初始化模型
            logger.info(f"正在加载ASR模型: {model_dir}")
            
            # 构建VAD配置参数
            vad_kwargs = {
                "max_single_segment_time": int(self.vad_settings.get("max_speech_duration_s", 30) * 1000),  # 转换为毫秒
                "threshold": self.vad_settings.get("threshold", 0.3),
                "min_speech_duration_ms": self.vad_settings.get("min_speech_duration_ms", 100),
                "min_silence_duration_ms": self.vad_settings.get("min_silence_duration_ms", 300),
                "window_size_samples": self.vad_settings.get("window_size_samples", 1024),
                "speech_pad_ms": self.vad_settings.get("speech_pad_ms", 30),
            }
            
            self.model = AutoModel(
                model=model_dir,
                device="cuda" if use_gpu and self._is_gpu_available() else "cpu",
                batch_size=1,
                ncpu=4,
                vad_model="fsmn-vad",  # 添加VAD模型以提高语言检测准确性
                vad_kwargs=vad_kwargs,  # 使用配置的VAD参数
            )
            logger.info("ASR模型加载完成")

        except Exception as e:
            logger.error(f"初始化ASR模型失败: {str(e)}", exc_info=True)
            self.model = None  # 确保模型为None，这样recognize方法会报错
    
    def _is_gpu_available(self) -> bool:
        """检查GPU是否可用"""
        try:
            import torch
            return torch.cuda.is_available()
        except:
            return False
    
    def _clean_sensevoice_output(self, raw_text: str) -> str:
        """清理SenseVoice模型输出的特殊标记
        
        Args:
            raw_text: 原始识别结果，包含特殊标记
            
        Returns:
            清理后的纯文本
        """
        try:
            # 尝试使用SenseVoice的rich transcription后处理
            from funasr.utils.postprocess_utils import rich_transcription_postprocess
            cleaned_text = rich_transcription_postprocess(raw_text)
            logger.debug(f"SenseVoice rich后处理: '{raw_text}' -> '{cleaned_text}'")
            return cleaned_text
        except ImportError:
            # 如果没有rich_transcription_postprocess，使用正则表达式清理
            import re
            cleaned_text = re.sub(r'<\|[^|]*\|>', '', raw_text)
            cleaned_text = cleaned_text.strip()
            logger.debug(f"SenseVoice正则清理: '{raw_text}' -> '{cleaned_text}'")
            return cleaned_text
        except Exception as e:
            logger.warning(f"SenseVoice后处理失败，使用正则清理: {str(e)}")
            import re
            cleaned_text = re.sub(r'<\|[^|]*\|>', '', raw_text)
            cleaned_text = cleaned_text.strip()
            return cleaned_text
    
    def recognize(self, audio_data: bytes, audio_format: str = "auto") -> Dict[str, Any]:
        """识别音频

        Args:
            audio_data: 音频数据
            audio_format: 音频格式，可选值："auto"(自动检测), "wav", "pcm"

        Returns:
            识别结果
        """
        if self.model is None:
            return {"success": False, "error": "ASR模型未初始化"}

        try:
            # FunASR支持直接接收numpy数组，避免格式转换
            if audio_format.lower() in ["auto", "pcm"]:
                # 假设音频数据是16-bit PCM格式，转换为float32并归一化到[-1, 1]
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                logger.info(f"直接使用numpy数组识别，样本数: {len(audio_np)}")
                
                # 执行识别，使用numpy数组作为输入
                result = self.model.generate(
                    input=audio_np,
                    fs=16000,  # 采样率16kHz
                    language="zh",  # 强制指定中文
                    use_itn=False,   # 不使用逆文本规范化，保持原始输出
                    batch_size_s=60,  # 动态批处理
                    merge_vad=self.vad_settings.get("merge_vad", True),   # 合并VAD分割的短音频片段
                    merge_length_s=self.vad_settings.get("merge_length_s", 15)  # 合并长度
                )
            else:
                # 对于其他格式，如果需要文件方式，使用临时文件
                temp_path = tempfile.mktemp(suffix=f".{audio_format}")
                with open(temp_path, 'wb') as f:
                    f.write(audio_data)
                
                logger.info(f"使用临时文件识别，格式: {audio_format}")
                
                # 执行识别
                result = self.model.generate(
                    input=temp_path,
                    language="zh",  # 强制指定中文
                    use_itn=False,   # 不使用逆文本规范化，保持原始输出
                    batch_size_s=60,  # 动态批处理
                    merge_vad=self.vad_settings.get("merge_vad", True),   # 合并VAD分割的短音频片段
                    merge_length_s=self.vad_settings.get("merge_length_s", 15)  # 合并长度
                )
                
                # 删除临时文件
                os.unlink(temp_path)
            
            # 提取识别文本 - SenseVoice结果格式
            if isinstance(result, list) and len(result) > 0:
                raw_text = result[0].get("text", "")
                # 清理SenseVoice的特殊标记，只保留实际文本
                text = self._clean_sensevoice_output(raw_text)
                logger.info(f"识别结果: {text}")
            else:
                text = ""
                logger.warning("未获取到识别结果或结果格式异常")
            
            return {
                "success": True,
                "text": text
            }
            
        except Exception as e:
            logger.error(f"语音识别失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"语音识别失败: {str(e)}"
            }

    
    def decode_audio(self, base64_audio: str) -> Optional[bytes]:
        """解码Base64编码的音频数据

        Args:
            base64_audio: Base64编码的音频数据

        Returns:
            解码后的音频数据
        """
        try:
            return base64.b64decode(base64_audio)
        except Exception as e:
            logger.error(f"解码音频数据失败: {str(e)}")
            return None


# 全局单例
_asr_service = None


def get_asr_service() -> ASRService:
    """获取ASR服务实例

    Returns:
        ASR服务实例
    """
    global _asr_service
    if _asr_service is None:
        _asr_service = ASRService()
    return _asr_service
