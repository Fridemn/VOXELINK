"""
大语言模型服务

该模块提供与大语言模型API的交互功能
"""

import logging
import asyncio
import aiohttp
import json
import re
from typing import Optional, Dict, Any
from app.core.stt_config import get_settings

logger = logging.getLogger(__name__)

class LLMService:
    """大语言模型服务类"""
    
    def __init__(self):
        self.settings = get_settings()
        self.llm_config = self.settings.get("llm", {})
        self.api_url = self.llm_config.get("api_url", "")
        self.enabled = self.llm_config.get("enabled", False)
        
    def clean_asr_text(self, text: str) -> str:
        """
        清理ASR识别结果中的标记和噪音
        
        Args:
            text: 原始ASR识别文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return ""
            
        # 移除SenseVoice的特殊标记
        # 匹配模式如: <|zh|><|NEUTRAL|><|Speech|><|woitn|>
        cleaned_text = re.sub(r'<\|[^|]*\|>', '', text)
        
        # 移除多余的空格和换行
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        logger.info(f"文本清理: '{text}' -> '{cleaned_text}'")
        return cleaned_text
        
    async def send_to_llm(self, message: str, token: str, tts: Optional[bool] = None) -> Optional[Dict[Any, Any]]:
        """
        将识别到的文本发送给大语言模型
        
        Args:
            message: 识别到的文本内容
            token: 用户token
            
        Returns:
            LLM的响应结果，如果失败返回None
        """
        logger.info(f"LLM服务调用开始 - enabled: {self.enabled}, api_url: {self.api_url}, token长度: {len(token)}")
        
        if not self.enabled:
            logger.warning("LLM服务未启用")
            return None
            
        if not self.api_url:
            logger.warning("LLM API URL未配置")
            return None
            
        if not token:
            logger.warning("用户token为空")
            return None
            
        # 清理ASR文本
        cleaned_message = self.clean_asr_text(message)
        # tts参数优先使用传入值，否则用配置
        if tts is None:
            tts = self.llm_config.get("tts", True)
        if not cleaned_message:
            logger.warning("清理后的文本为空，跳过LLM调用")
            return None
            
        try:
            # 准备请求URL（token作为query参数）
            url_with_token = f"{self.api_url}?token={token}"
            
            # 准备请求体（application/x-www-form-urlencoded格式）
            form_data = {
                "model": self.llm_config.get("model", "gpt-4o-mini"),
                "message": cleaned_message,
                "role": self.llm_config.get("role", "user"),
                "stream": str(self.llm_config.get("stream", True)).lower(),  # 转换为字符串
                "tts": str(tts).lower()  # 新增tts参数
            }
            
            logger.info(f"发送给LLM: {cleaned_message}")
            logger.info(f"请求URL: {url_with_token}")
            logger.info(f"表单数据: {form_data}")
            
            # 从配置中获取超时设置
            total_timeout = self.llm_config.get("timeout", 60)
            connect_timeout = self.llm_config.get("connect_timeout", 10)
            read_timeout = self.llm_config.get("read_timeout", 50)
            
            # 设置超时
            timeout = aiohttp.ClientTimeout(
                total=total_timeout,
                connect=connect_timeout,
                sock_read=read_timeout
            )
            
            logger.info(f"使用超时配置 - 总超时: {total_timeout}s, 连接超时: {connect_timeout}s, 读取超时: {read_timeout}s")
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url_with_token,
                    data=form_data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                ) as response:
                    if response.status == 200:
                        # 检查响应类型
                        content_type = response.headers.get('content-type', '')
                        
                        if 'text/event-stream' in content_type:
                            # 处理流式响应
                            logger.info("处理流式响应")
                            return await self._handle_stream_response(response)
                        else:
                            # 处理JSON响应
                            logger.info("处理JSON响应")
                            result = await response.json()
                            logger.info(f"LLM响应成功: {result}")
                            return result
                    else:
                        error_text = await response.text()
                        logger.error(f"LLM API错误 {response.status}: {error_text}")
                        return {
                            "error": f"API错误 {response.status}",
                            "details": error_text
                        }
                        
        except asyncio.TimeoutError:
            logger.error("LLM API请求超时")
            return {
                "error": "请求超时",
                "details": "LLM API响应超时"
            }
        except aiohttp.ClientConnectorError as e:
            logger.error(f"LLM API连接错误: {e}")
            return {
                "error": "连接失败", 
                "details": f"无法连接到LLM服务: {str(e)}"
            }
        except Exception as e:
            logger.error(f"LLM API请求异常: {e}")
            return {
                "error": "请求异常",
                "details": str(e)
            }

    async def _handle_stream_response(self, response) -> Optional[Dict[Any, Any]]:
        """
        处理流式响应 (Server-Sent Events)
        """
        try:
            full_text = ""
            token_info = None
            
            async for line in response.content:
                line = line.decode('utf-8').strip()
                
                if line.startswith('data: '):
                    data_str = line[6:]  # 移除 "data: " 前缀
                    
                    if data_str == '[DONE]':
                        # 流结束
                        break
                    
                    try:
                        data = json.loads(data_str)
                        
                        if 'text' in data:
                            # 累积文本
                            full_text += data['text']
                            
                        if 'token_info' in data:
                            # 保存token信息
                            token_info = data['token_info']
                            
                    except json.JSONDecodeError:
                        # 跳过无效的JSON行
                        continue
            
            # 构建完整响应
            result = {
                "text": full_text,
                "stream": True
            }
            
            if token_info:
                result["token_info"] = token_info
            
            logger.info(f"流式响应处理完成，文本长度: {len(full_text)}")
            return result
            
        except Exception as e:
            logger.error(f"处理流式响应异常: {e}")
            return {
                "error": "流式响应处理失败",
                "details": str(e)
            }

# 单例实例
_llm_service = None

def get_llm_service() -> LLMService:
    """获取LLM服务实例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
