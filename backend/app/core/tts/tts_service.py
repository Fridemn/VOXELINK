import asyncio
import os
import sys
import tempfile
import json
from pathlib import Path
from loguru import logger

from app import app_config

# 添加GSVI路径到sys.path
gsvi_path = Path(__file__).parent.parent / "gsvi"
if str(gsvi_path) not in sys.path:
    sys.path.insert(0, str(gsvi_path))

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
    if config is not None:
        return config

    # 从主配置目录加载
    config_path = Path(__file__).parent.parent.parent.parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"TTS配置文件加载成功: {config_path}")
            return config
        except Exception as e:
            logger.warning(f"TTS配置文件加载失败: {e}")

    # 默认配置
    config = {
        "inference": {
            "default_character": "march7",
            "default_mood": "normal",
            "default_language": "chinese",
            "default_how_to_cut": "no_cut",
            "default_top_k": 15,
            "default_top_p": 1.0,
            "default_temperature": 1.0,
            "default_ref_free": False,
            "default_speed": 1.0,
            "default_if_freeze": False,
            "default_sample_steps": 8,
            "default_if_sr": False,
            "default_pause_second": 0.3
        },
        "characters": {
            "march7": {
                "name": "三月七",
                "default_mood": "normal",
                "moods": {
                    "normal": {
                        "audio_path": "GPT_SoVITS/ref_audio/march7/nomal.wav",
                        "prompt_text": "裂界，确实会对周围空间造成很多影响啦。空间站电子设备这么多，是不是经常发生短路？",
                        "language": "chinese"
                    },
                    "excited": {
                        "audio_path": "GPT_SoVITS/ref_audio/march7/excited.wav",
                        "prompt_text": "哇！太棒了！我超级兴奋！",
                        "language": "chinese"
                    },
                    "confused": {
                        "audio_path": "GPT_SoVITS/ref_audio/march7/confused.wav",
                        "prompt_text": "诶？这是什么情况？我有点困惑。",
                        "language": "chinese"
                    }
                }
            }
        }
    }
    return config


async def text_to_speech_stream(text_chunk: str, character: str = "march7", mood: str = "normal"):
    """
    异步调用TTS服务进行语音合成，并处理流式响应。

    Args:
        text_chunk (str): 需要合成的文本块。
        character (str): 角色名称。
        mood (str): 情绪。
    """
    if not GSVI_AVAILABLE:
        logger.warning("GSVI模块不可用，跳过语音合成。")
        return

    try:
        # 加载配置
        tts_config = load_tts_config()
        inference_config = tts_config.get("inference", {})
        characters_config = tts_config.get("characters", {})

        # 获取默认角色和情绪
        default_character = character or inference_config.get("default_character", "march7")
        character_config = characters_config.get(default_character, {})

        if not character_config:
            # 如果找不到指定角色，使用第一个可用角色
            if characters_config:
                default_character = list(characters_config.keys())[0]
                character_config = characters_config[default_character]
            else:
                logger.error("未找到任何角色配置")
                return

        # 获取情绪配置
        default_mood = mood or character_config.get("default_mood", "normal")
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
        prompt_text = mood_config.get("prompt_text", "")
        prompt_language_en = mood_config.get("language", "chinese")
        prompt_language = map_language_param(prompt_language_en)

        if not ref_audio_path or not os.path.exists(ref_audio_path):
            logger.error(f"参考音频文件不存在: {ref_audio_path}")
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
            sovits_path = default_models.get("sovits_path", "GPT_SoVITS/models/SoVITS_weights_v4/March7_e10_s4750_l32.pth")
            gpt_path = default_models.get("gpt_path", "GPT_SoVITS/models/GPT_weights_v4/March7-e15.ckpt")
            
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
            return

        # 将音频数据保存到临时文件
        import torch
        import torchaudio
        import numpy as np

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_output:
            # 确保音频数据是正确的格式
            if isinstance(audio_data, np.ndarray):
                # 转换为 torch tensor
                audio_tensor = torch.from_numpy(audio_data.astype(np.float32)) / 32767.0
            else:
                audio_tensor = audio_data
            # 保存音频文件
            torchaudio.save(temp_output.name, audio_tensor.unsqueeze(0), sr, format="wav")
            output_path = temp_output.name

        logger.info(f"成功为文本 '{text_chunk}' 生成TTS音频，角色: {default_character}，情绪: {default_mood}，文件: {output_path}")

        # 这里可以根据需要处理音频文件，比如保存到指定位置或返回给调用者
        # 目前暂时保存到临时文件，后续可以扩展为返回音频数据或保存到数据库

    except Exception as e:
        logger.error(f"处理TTS请求时发生未知错误: {e}")
        import traceback
        logger.error(traceback.format_exc())


# 示例用法
async def main():
    """测试TTS服务调用的示例函数"""
    test_text = "你好，这是一个测试。"
    await text_to_speech_stream(test_text)


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main()) 