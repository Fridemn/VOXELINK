import asyncio
import os
import sys
import tempfile
import json
from pathlib import Path
from loguru import logger

from ... import app_config

# 添加GSVI路径到sys.path
tts_path = Path(__file__).parent.parent / "tts"
if str(tts_path) not in sys.path:
    sys.path.insert(0, str(tts_path))

# 导入GSVI核心推理模块
try:
    from core_inference import get_tts_wav, load_models, dict_language
    from router import map_language_param, map_cut_method_param
    GSVI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"无法导入GSVI模块: {e}")
    GSVI_AVAILABLE = False

# 全局配置变量
config = None

def set_tts_config(global_config):
    """设置TTS配置"""
    global config
    config = global_config

def load_tts_config():
    """加载TTS配置文件"""
    global config
    logger.info(f"load_tts_config called, global config is None: {config is None}")
    if config is not None:
        logger.info(f"Returning cached config, has characters: {'characters' in config}")
        return config

    try:
        from ...config.app_config import get_app_config
        app_config = get_app_config()
        
        # 从统一配置中获取TTS相关配置
        tts_config = app_config.get("tts_config", {})
        characters_config = app_config.get("characters", {})
        pretrained_models = app_config.get("pretrained_models", {})
        
        logger.info(f"从统一配置加载 - tts_config: {bool(tts_config)}, characters_config: {bool(characters_config)}, pretrained_models: {bool(pretrained_models)}")
        logger.info(f"characters keys: {list(characters_config.keys()) if characters_config else 'None'}")
        
        # 验证必需的配置项
        if not tts_config.get("default_character"):
            raise ValueError("配置中必须指定 tts_config.default_character")
        if not tts_config.get("default_mood"):
            raise ValueError("配置中必须指定 tts_config.default_mood")
        if not characters_config:
            raise ValueError("配置中必须包含 characters 配置")
        
        config = {
            "inference": {
                "default_character": tts_config["default_character"],
                "default_mood": tts_config["default_mood"],
                "default_language": tts_config.get("default_language", "chinese"),
                "default_how_to_cut": tts_config.get("default_how_to_cut", "no_cut"),
                "default_top_k": tts_config.get("default_top_k", 15),
                "default_top_p": tts_config.get("default_top_p", 1.0),
                "default_temperature": tts_config.get("default_temperature", 1.0),
                "default_ref_free": tts_config.get("default_ref_free", False),
                "default_speed": tts_config.get("default_speed", 1.0),
                "default_if_freeze": tts_config.get("default_if_freeze", False),
                "default_sample_steps": tts_config.get("default_sample_steps", 8),
                "default_if_sr": tts_config.get("default_if_sr", False),
                "default_pause_second": tts_config.get("default_pause_second", 0.3)
            },
            "characters": characters_config,
            "default_models": {
                "sovits_path": pretrained_models.get("sovits_v4"),
                "gpt_path": pretrained_models.get("gpt_v4")
            }
        }
        logger.info("从统一配置加载TTS配置成功")
        logger.info(f"角色配置: {list(characters_config.keys()) if characters_config else '空'}")
        return config
    except Exception as e:
        logger.warning(f"无法从统一配置加载配置，使用全局配置: {e}")
        
    # 如果统一配置加载失败，使用全局配置（如果已设置）
    if config is not None:
        logger.info("使用全局TTS配置")
        return config
        
    # 如果都没有，抛出错误
    raise RuntimeError(f"无法加载TTS配置: {e}")


async def text_to_speech_stream(text_chunk: str, character: str = None, mood: str = None):
    """
    异步调用TTS服务进行语音合成，并返回音频数据。

    Args:
        text_chunk (str): 需要合成的文本块。
        character (str): 角色名称，如果为None则使用配置中的默认值。
        mood (str): 情绪，如果为None则使用配置中的默认值。

    Returns:
        tuple: (sample_rate, audio_data) 或 None如果失败
    """
    if not GSVI_AVAILABLE:
        logger.warning("GSVI模块不可用，跳过语音合成。")
        return

    try:
        # 加载配置
        tts_config = load_tts_config()
        inference_config = tts_config.get("inference", {})
        characters_config = tts_config.get("characters", {})

        logger.info(f"TTS配置加载: characters_config keys = {list(characters_config.keys()) if characters_config else 'None'}")
        logger.info(f"默认角色: {inference_config['default_character']}")

        # 获取默认角色和情绪
        default_character = character or inference_config["default_character"]
        character_config = characters_config.get(default_character, {})

        logger.info(f"查找角色 '{default_character}': {bool(character_config)}")

        if not character_config:
            logger.error(f"未找到角色配置: {default_character}")
            logger.error(f"可用角色: {list(characters_config.keys()) if characters_config else 'None'}")
            return

        # 获取情绪配置
        default_mood = mood or character_config.get("default_mood", inference_config["default_mood"])
        moods_config = character_config.get("moods", {})
        mood_config = moods_config.get(default_mood)

        if not mood_config:
            # 如果找不到指定情绪，尝试使用normal
            mood_config = moods_config.get("normal")
            if not mood_config and moods_config:
                # 如果连normal都没有，使用第一个可用情绪
                mood_config = list(moods_config.values())[0]
            if not mood_config:
                logger.error(f"角色 {default_character} 未找到情绪配置")
                return

        # 获取参考音频路径和文本
        ref_audio_path = mood_config.get("audio_path")
        if ref_audio_path and not os.path.isabs(ref_audio_path):
            # 如果是相对路径，相对于项目根目录
            if ref_audio_path.startswith("backend/"):
                # 如果以backend/开头，从项目根目录开始
                project_root = Path(__file__).parent.parent.parent.parent.parent
                ref_audio_path = project_root / ref_audio_path
            else:
                # 否则相对于backend目录
                backend_dir = Path(__file__).parent.parent.parent.parent
                ref_audio_path = backend_dir / ref_audio_path
            logger.info(f"backend_dir: {backend_dir if 'backend_dir' in locals() else 'N/A'}")
            logger.info(f"project_root: {project_root if 'project_root' in locals() else 'N/A'}")
            logger.info(f"ref_audio_path before: {mood_config.get('audio_path')}")
            logger.info(f"ref_audio_path after: {ref_audio_path}")
        
        ref_audio_path = str(ref_audio_path)
        prompt_text = mood_config.get("prompt_text", "")
        prompt_language_en = mood_config.get("language", "chinese")
        prompt_language = map_language_param(prompt_language_en)

        logger.info(f"检查音频文件: {ref_audio_path}")
        if not ref_audio_path or not os.path.exists(ref_audio_path):
            logger.error(f"参考音频文件不存在: {ref_audio_path}")
            logger.error(f"当前工作目录: {os.getcwd()}")
            return

        # 其他参数从配置文件读取并映射
        text_language_en = inference_config.get("default_language", "chinese")
        text_language = map_language_param(text_language_en)

        how_to_cut_en = inference_config.get("default_how_to_cut", "no_cut")
        how_to_cut = map_cut_method_param(how_to_cut_en)

        # 从配置文件读取固定参数
        top_k = inference_config.get("default_top_k", 15)
        top_p = inference_config.get("default_top_p", 1.0)
        temperature = inference_config.get("default_temperature", 1.0)
        ref_free = inference_config.get("default_ref_free", False)
        speed = inference_config.get("default_speed", 1.0)
        if_freeze = inference_config.get("default_if_freeze", False)
        sample_steps = inference_config.get("default_sample_steps", 8)
        if_sr = inference_config.get("default_if_sr", False)
        pause_second = inference_config.get("default_pause_second", 0.3)

        logger.info(f"使用角色: {default_character}, 情绪: {default_mood}, 参考音频: {ref_audio_path}")

        # 确保模型已加载
        if not hasattr(sys.modules.get('core_inference'), 't2s_model') or sys.modules['core_inference'].t2s_model is None:
            # 加载默认模型
            default_models = tts_config.get("default_models", {})
            sovits_path = default_models.get("sovits_path")
            gpt_path = default_models.get("gpt_path")
            
            if not sovits_path or not gpt_path:
                logger.error("config.json 中必须指定 pretrained_models.sovits_v4 和 pretrained_models.gpt_v4")
                return
            
            if os.path.exists(sovits_path) and os.path.exists(gpt_path):
                logger.info(f"加载TTS模型: SoVITS={sovits_path}, GPT={gpt_path}")
                load_models(gpt_path, sovits_path)
            else:
                logger.error(f"TTS模型文件不存在: SoVITS={sovits_path}, GPT={gpt_path}")
                return

        # 调用TTS函数
        result_generator = get_tts_wav(
            ref_wav_path=ref_audio_path,
            prompt_text=prompt_text,
            prompt_language=prompt_language,
            text=text_chunk,
            text_language=text_language,
            how_to_cut=how_to_cut,
            top_k=top_k,
            top_p=top_p,
            temperature=temperature,
            ref_free=ref_free,
            speed=speed,
            if_freeze=if_freeze,
            inp_refs=None,
            sample_steps=sample_steps,
            if_sr=if_sr,
            pause_second=pause_second,
        )

        # 获取生成的音频
        sr, audio_data = next(result_generator)

        if sr is None or audio_data is None:
            logger.error("音频生成失败")
            return None

        # 将音频数据转换为适合传输的格式
        import torch
        import torchaudio
        import numpy as np
        import io

        # 确保音频数据是正确的格式
        if isinstance(audio_data, np.ndarray):
            # 转换为 torch tensor
            audio_tensor = torch.from_numpy(audio_data.astype(np.float32)) / 32767.0
        else:
            audio_tensor = audio_data

        # 创建内存缓冲区来保存音频
        buffer = io.BytesIO()
        torchaudio.save(buffer, audio_tensor.unsqueeze(0), sr, format="wav")
        audio_bytes = buffer.getvalue()

        logger.info(f"成功为文本 '{text_chunk}' 生成TTS音频，角色: {default_character}，情绪: {default_mood}，大小: {len(audio_bytes)} 字节")

        return sr, audio_bytes

    except Exception as e:
        logger.error(f"处理TTS请求时发生未知错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


# 示例用法
async def main():
    """测试TTS服务调用的示例函数"""
    test_text = "你好，这是一个测试。"
    await text_to_speech_stream(test_text)


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main()) 