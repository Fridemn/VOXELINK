"""
app/core/llm/chat.py
大语言模型（LLM）基础接口与实现。
- 提供多种LLM聊天服务的API接口。
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any, Dict, List, Optional

import aiohttp
import json
import traceback
from pydantic import BaseModel
from loguru import logger


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMResponse(BaseModel):
    text: str
    raw_response: Optional[Dict[str, Any]] = None


class LLMErrorResponse(LLMResponse):
    def __init__(self, reason: str):
        super().__init__(text=f"LLM Error: {reason}")
        self.raw_response = {"error": reason}


class LLMConfig(BaseModel):
    api_key: str
    base_url: str
    model_name: str


class BaseLLM(ABC):
    def __init__(self, llm_config: LLMConfig):
        self.api_key = llm_config.api_key
        self.base_url = llm_config.base_url
        self.model_name = llm_config.model_name

    @abstractmethod
    async def chat_completion(self, messages: List[LLMMessage]) -> LLMResponse:
        raise NotImplementedError()

    @abstractmethod
    async def chat_completion_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        raise NotImplementedError()


class OpenAILLM(BaseLLM):
    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)

        logger.info(f"Created OpenAI LLM instance - model: {self.model_name}, base_url: {self.base_url}")

    async def chat_completion(self, messages: List[LLMMessage]) -> LLMResponse:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {"model": self.model_name, "messages": [m.dict() for m in messages], "stream": False}

            logger.debug(f"OpenAI chat completion payload: {payload}")

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload) as response:
                    # 检查响应状态码
                    response.raise_for_status()

                    # 检查响应结构
                    result = await response.json()
                    if "choices" not in result or result["choices"] is None:
                        raise ValueError("Required 'choices' key in API response")

                    return LLMResponse(
                        text=result["choices"][0]["message"]["content"],
                        raw_response=result,
                    )
        except Exception as e:
            logger.error(f"OpenAI chat completion API failure: {type(e).__name__} - {str(e)}")
            logger.error(traceback.format_exc())
            return LLMErrorResponse(reason="(OpenAI) " + str(e))

    async def chat_completion_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {"model": self.model_name, "messages": [m.dict() for m in messages], "stream": True}

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload) as response:
                    # 检查响应状态码
                    response.raise_for_status()

                    # 调试第一块原始响应
                    first_chunk = await response.content.readany()
                    first_text = first_chunk.decode("utf-8", errors="replace")

                    # 处理第一块
                    lines = first_text.split("\n")
                    for line in lines:
                        if not line.strip():
                            continue

                        if line.startswith("data: "):
                            line = line[6:]
                            if line == "[DONE]":
                                break

                            try:
                                chunk = json.loads(line)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"]:
                                        yield delta["content"]
                            except json.JSONDecodeError as e:
                                raise e

                    # 继续处理剩余流
                    async for line in response.content:
                        line = line.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue

                        if line.startswith("data: "):
                            line = line[6:]
                            if line == "[DONE]":
                                break

                            try:
                                chunk = json.loads(line)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"]:
                                        yield delta["content"]
                            except json.JSONDecodeError as e:
                                raise e
        except Exception as e:
            logger.error(f"OpenAI chat completion API failure: {type(e).__name__} - {str(e)}")
            logger.error(traceback.format_exc())
            yield LLMErrorResponse(reason="(OpenAI) " + str(e)).text


class AnthropicLLM(BaseLLM):
    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config)

        logger.info(f"Created Anthropic LLM instance - model: {self.model_name}, base_url: {self.base_url}")

    async def chat_completion(self, messages: List[LLMMessage]) -> LLMResponse:
        try:
            headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}

            # 将 OpenAI 消息格式转换为 Anthropic 格式
            claude_messages = []
            for msg in messages:
                claude_messages.append({"role": msg.role, "content": msg.content})

            payload = {"model": self.model_name, "messages": claude_messages, "max_tokens": 1000}

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/messages", headers=headers, json=payload) as response:
                    # 检查响应状态码
                    response.raise_for_status()

                    result = await response.json()
                    if "error" in result:
                        raise Exception(result["error"])

                    return LLMResponse(
                        text=result["content"][0]["text"],
                        raw_response=result,
                    )
        except Exception as e:
            logger.error(f"Anthropic chat completion API failure: {type(e).__name__} - {str(e)}")
            logger.error(traceback.format_exc())
            return LLMErrorResponse(reason="(Anthropic) " + str(e))

    async def chat_completion_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        # Anthropic流式响应实现可以后续添加
        yield "Anthropic流式响应尚未实现"


class OllamaLLM(BaseLLM):
    def __init__(self, llm_config: LLMConfig):
        # Ollama 通常不需要 API key，但保留这个字段以保持接口一致性
        super().__init__(llm_config)

        logger.info(f"Created Ollama LLM instance - model: {self.model_name}, base_url: {self.base_url}")

    async def chat_completion(self, messages: List[LLMMessage]) -> LLMResponse:
        try:
            headers = {"Content-Type": "application/json"}
            payload = {"model": self.model_name, "messages": [m.dict() for m in messages], "stream": False}

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/chat", headers=headers, json=payload) as response:
                    response.raise_for_status()  # 检查响应状态码

                    result = await response.json()
                    if "error" in result:
                        raise Exception(f"Ollama API error: {result['error']}")

                    # Ollama API 通常会在 response 包含 message 字段
                    return LLMResponse(
                        text=result.get("message", {}).get("content", ""),
                        raw_response=result,
                    )
        except Exception as e:
            logger.error(f"Ollama chat completion API failure: {type(e).__name__} - {str(e)}")
            logger.error(traceback.format_exc())
            return LLMErrorResponse(reason="(Ollama) " + str(e))

    async def chat_completion_stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        try:
            headers = {"Content-Type": "application/json"}

            ollama_messages = [m.dict() for m in messages]

            payload = {"model": self.model_name, "messages": ollama_messages, "stream": True}

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/chat", headers=headers, json=payload) as response:
                    response.raise_for_status()  # 检查响应状态码

                    async for chunk in response.content:
                        if not chunk:
                            continue

                        try:
                            data = json.loads(chunk)
                            # Ollama 的流式响应通常会包含 message 字段
                            if "message" in data and "content" in data["message"]:
                                content = data["message"]["content"]
                                if content:
                                    yield content
                            # 处理另一种可能的响应格式，直接包含 'response' 字段
                            elif "response" in data:
                                content = data["response"]
                                if content:
                                    yield content
                        except json.JSONDecodeError as e:
                            raise e
        except Exception as e:
            logger.error(f"Ollama chat completion API failure: {type(e).__name__} - {str(e)}")
            logger.error(traceback.format_exc())
            yield LLMErrorResponse(reason="(Ollama) " + str(e)).text
