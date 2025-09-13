import asyncio
import httpx
from loguru import logger

from app import app_config

# 从配置中获取TTS服务URL
TTS_BASE_URL = app_config.get("tts_config", {}).get("base_url")


async def text_to_speech_stream(text_chunk: str, user_token: str, character: str = "march7", mood: str = "normal"):
    """
    异步调用TTS服务进行语音合成，并处理流式响应。

    Args:
        text_chunk (str): 需要合成的文本块。
        user_token (str): 用于WebSocket推送的用户token。
        character (str): 角色名称。
        mood (str): 情绪。
    """
    if not TTS_BASE_URL:
        logger.warning("TTS服务URL未配置，跳过语音合成。")
        return

    # 准备请求数据
    data = {
        "text": text_chunk,
        "character": character,
        "mood": mood,
        "text_language": "chinese",
        "how_to_cut": "no_cut",
        "token": user_token,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TTS_BASE_URL}/tts",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()  # 确保请求成功
            logger.info(f"成功为文本 '{text_chunk}' 请求TTS，角色: {character}，情绪: {mood}")
            logger.debug(f"TTS服务响应: {response.json()}")

    except httpx.RequestError as e:
        logger.error(f"请求TTS服务失败: {e}")
    except Exception as e:
        logger.error(f"处理TTS请求时发生未知错误: {e}")


# 示例用法
async def main():
    """测试TTS服务调用的示例函数"""
    test_token = "your_test_token"  # 替换为有效的测试token
    test_text = "你好，这是一个测试。"
    await text_to_speech_stream(test_text, test_token)


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main()) 