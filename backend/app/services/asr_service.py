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
        from app.config.default import DEFAULT_CONFIG
        return DEFAULT_CONFIG.get("stt", {})
    except Exception as e:
        logger.warning(f"无法加载后端配置，使用空配置: {e}")
        return {}


# 配置日志
logger = logging.getLogger("asr_service")


class ASRService:
    """语音识别服务类"""
    
    def __init__(self):
        """初始化语音识别服务"""
        self.settings = get_stt_settings()
        self.model = None
        self.vad = None
        
        # 初始化ASR模型
        self._init_asr_model()
        
        # 初始化VAD
        if self.settings.get("use_vad", True):
            self._init_vad()
    
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
              # 初始化模型            logger.info(f"正在加载ASR模型: {model_dir}")
            self.model = AutoModel(
                model=model_dir,
                device="cuda" if use_gpu and self._is_gpu_available() else "cpu",
                batch_size=1,
                ncpu=4,
                vad_model="fsmn-vad",  # 添加VAD模型以提高语言检测准确性
                vad_kwargs={"max_single_segment_time": 30000},  # VAD配置
            )
            logger.info("ASR模型加载完成")

        except Exception as e:
            logger.error(f"初始化ASR模型失败: {str(e)}", exc_info=True)
            self.model = None  # 确保模型为None，这样recognize方法会报错
    
    def _init_vad(self):
        """初始化VAD"""
        try:
            import torch
            
            logger.info("正在加载VAD模型")
            self.vad_model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                onnx=False
            )
            self.get_speech_timestamps = utils[0]
            self.threshold = self.settings.get("vad_threshold", 0.3)  # 语音检测阈值
            self.min_speech_duration = self.settings.get("vad_min_speech_duration", 0.25)  # 最小语音持续时间(秒)
            logger.info("VAD模型加载完成")
            
        except Exception as e:
            logger.error(f"初始化VAD失败: {str(e)}", exc_info=True)
            self.vad_model = None
    
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
            # 如果明确指定了PCM格式，则直接使用PCM数据识别
            if audio_format.lower() == "pcm":
                return self._recognize_pcm(audio_data)
                
            # 否则使用文件方式识别（WAV格式）
            import wave
            import struct
            
            # 假设音频是16kHz, 16-bit, 单声道的原始PCM数据
            temp_path = tempfile.mktemp(suffix=".wav")
            is_wav_format = False
            
            # 检查是否已经是WAV格式
            try:
                with io.BytesIO(audio_data) as audio_io:
                    # 检查WAV文件魔数(RIFF头和WAVE标识)
                    riff_header = audio_io.read(4)
                    audio_io.seek(8)
                    wave_header = audio_io.read(4)
                    
                    if riff_header == b'RIFF' and wave_header == b'WAVE':
                        logger.info("接收到WAV格式音频数据 (检测到RIFF/WAVE标识)，无需转换")
                        with open(temp_path, 'wb') as f:
                            f.write(audio_data)
                        is_wav_format = True
            except Exception as e:
                logger.debug(f"检查WAV标识时发生错误: {str(e)}")
            
            # 如果不是WAV格式，则尝试使用wave库打开
            if not is_wav_format:
                try:
                    with wave.open(io.BytesIO(audio_data), 'rb') as wav_check:
                        # 如果能打开，说明已经是WAV格式，直接写入文件
                        logger.info("接收到WAV格式音频数据 (wave库成功打开)，无需转换")
                        with open(temp_path, 'wb') as f:
                            f.write(audio_data)
                        is_wav_format = True
                except Exception as e:
                    logger.debug(f"使用wave库打开WAV数据时发生错误: {str(e)}")
            
            # 如果仍不是WAV格式，则创建新的WAV文件
            if not is_wav_format:
                # 不是WAV格式，创建一个新的WAV文件
                logger.info("音频数据不是WAV格式，转换为WAV格式")
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # 单声道
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(16000)  # 16kHz
                    
                    # 如果输入是原始PCM数据，直接写入
                    if len(audio_data) % 2 == 0:  # 检查是否是偶数字节（16位样本）
                        wav_file.writeframes(audio_data)
                    else:
                        # 如果不是正确的PCM格式，尝试转换
                        logger.warning("音频数据格式异常，尝试转换")
                        # 假设是Float32格式，转换为Int16
                        try:
                            import numpy as np
                            samples = np.frombuffer(audio_data, dtype=np.float32)
                            samples = (samples * 32767).astype(np.int16)
                            wav_file.writeframes(samples.tobytes())
                        except:
                            # 如果转换失败，记录日志但仍然尝试使用原始数据
                            logger.error("音频数据转换失败，使用原始数据")
                            wav_file.writeframes(audio_data)
            
            # 检查临时文件大小
            file_size = os.path.getsize(temp_path)
            logger.info(f"临时WAV文件大小: {file_size} 字节，是否为原始WAV格式: {is_wav_format}")
            
            # 执行识别
            result = self.model.generate(
                input=temp_path,
                language="zh",  # 强制指定中文
                use_itn=False,   # 不使用逆文本规范化，保持原始输出
                batch_size_s=60,  # 动态批处理
                merge_vad=True,   # 合并VAD分割的短音频片段
                merge_length_s=15  # 合并长度
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
    def _recognize_pcm(self, pcm_data: bytes) -> Dict[str, Any]:
        """直接识别PCM音频数据，避免WAV格式转换

        Args:
            pcm_data: PCM格式的音频数据

        Returns:
            识别结果
        """
        try:
            import wave
            
            # 创建临时文件但直接写入PCM数据
            # 注意：这种方式不写入WAV头，直接使用原始PCM数据
            temp_path = tempfile.mktemp(suffix=".pcm")
            
            with open(temp_path, 'wb') as f:
                f.write(pcm_data)
            
            # 记录PCM文件大小
            file_size = os.path.getsize(temp_path)
            logger.info(f"临时PCM文件大小: {file_size} 字节，直接PCM识别")
            
            # FunASR的一些实现可能支持直接处理PCM数据，但需要额外的参数
            # 这里我们尝试两种方式
            try:
                # 方式1: 尝试直接使用PCM文件路径，并指定额外参数
                result = self.model.generate(
                    input=temp_path, 
                    audio_format="pcm",
                    sample_rate=16000,
                    bits_per_sample=16,
                    channels=1,
                    language="zh",  # 强制指定中文
                    use_itn=False,   # 不使用逆文本规范化
                    batch_size_s=60,  # 动态批处理
                    merge_vad=True,   # 合并VAD分割的短音频片段
                    merge_length_s=15  # 合并长度
                )
            except Exception as e:
                logger.warning(f"直接PCM识别失败，尝试转换为WAV: {str(e)}")
                # 方式2: 如果不支持，则在内存中快速转换为WAV格式
                wav_path = temp_path + ".wav"
                
                # 使用wave库创建WAV文件
                with wave.open(wav_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # 单声道
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(16000)  # 16kHz
                    
                    # 读取PCM数据并写入
                    with open(temp_path, 'rb') as pcm_file:
                        pcm_data = pcm_file.read()
                        wav_file.writeframes(pcm_data)
                
                # 使用生成的WAV文件识别
                result = self.model.generate(
                    input=wav_path,
                    language="zh",  # 强制指定中文
                    use_itn=False,   # 不使用逆文本规范化
                    batch_size_s=60,  # 动态批处理
                    merge_vad=True,   # 合并VAD分割的短音频片段
                    merge_length_s=15  # 合并长度
                )
                
                # 删除临时WAV文件
                try:
                    os.unlink(wav_path)
                except:
                    pass
            
            # 删除临时PCM文件
            try:
                os.unlink(temp_path)
            except:
                pass
            
            # 提取识别文本 - SenseVoice结果格式
            if isinstance(result, list) and len(result) > 0:
                raw_text = result[0].get("text", "")
                # 清理SenseVoice的特殊标记，只保留实际文本
                text = self._clean_sensevoice_output(raw_text)
                logger.info(f"PCM直接识别结果: {text}")
            else:
                text = ""
                logger.warning("PCM识别未获取到结果或结果格式异常")
            
            return {
                "success": True,
                "text": text
            }
            
        except Exception as e:
            logger.error(f"PCM音频识别失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"PCM音频识别失败: {str(e)}"
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
