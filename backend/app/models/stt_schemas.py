"""
数据模型 - 定义应用中使用的数据模型
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AudioRecognitionRequest(BaseModel):
    """音频识别请求模型"""
    audio_data: str = Field(..., description="Base64编码的音频数据")
    check_voiceprint: bool = Field(True, description="是否执行声纹检查")
    only_register_user: bool = Field(False, description="是否仅识别已注册用户")
    identify_unregistered: bool = Field(False, description="是否识别未注册用户的语音")


class AudioRecognitionResponse(BaseModel):
    """音频识别响应模型"""
    success: bool = Field(..., description="是否成功")
    text: str = Field(None, description="识别的文本")
    error: Optional[str] = Field(None, description="错误信息")
    user_id: Optional[str] = Field(None, description="用户ID")
    user_name: Optional[str] = Field(None, description="用户名称")
    similarity: Optional[float] = Field(None, description="声纹相似度")


class VoiceprintRegistrationRequest(BaseModel):
    """声纹注册请求模型"""
    audio_data: str = Field(..., description="Base64编码的音频数据")
    user_id: str = Field(..., description="用户ID")
    user_name: Optional[str] = Field(None, description="用户名称")


class VoiceprintRegistrationResponse(BaseModel):
    """声纹注册响应模型"""
    success: bool = Field(..., description="是否成功")
    message: Optional[str] = Field(None, description="成功信息")
    error: Optional[str] = Field(None, description="错误信息")
    user_id: Optional[str] = Field(None, description="用户ID")
    user_name: Optional[str] = Field(None, description="用户名称")


class VoiceprintCompareRequest(BaseModel):
    """声纹比对请求模型"""
    audio_data1: str = Field(..., description="Base64编码的第一段音频数据")
    audio_data2: str = Field(..., description="Base64编码的第二段音频数据")


class VoiceprintCompareResponse(BaseModel):
    """声纹比对响应模型"""
    success: bool = Field(..., description="是否成功")
    similarity: Optional[float] = Field(None, description="相似度")
    is_same_person: Optional[bool] = Field(None, description="是否为同一人")
    error: Optional[str] = Field(None, description="错误信息")


class VoiceprintMatchRequest(BaseModel):
    """声纹匹配请求模型"""
    audio_data: str = Field(..., description="Base64编码的音频数据")


class VoiceprintMatchResponse(BaseModel):
    """声纹匹配响应模型"""
    success: bool = Field(..., description="是否成功")
    user_id: Optional[str] = Field(None, description="用户ID")
    user_name: Optional[str] = Field(None, description="用户名称")
    similarity: Optional[float] = Field(None, description="相似度")
    error: Optional[str] = Field(None, description="错误信息")


class VoiceprintRemoveRequest(BaseModel):
    """声纹删除请求模型"""
    user_id: str = Field(..., description="用户ID")


class VoiceprintRemoveResponse(BaseModel):
    """声纹删除响应模型"""
    success: bool = Field(..., description="是否成功")
    message: Optional[str] = Field(None, description="成功信息")
    error: Optional[str] = Field(None, description="错误信息")


class VoiceprintListResponse(BaseModel):
    """声纹列表响应模型"""
    success: bool = Field(..., description="是否成功")
    voiceprints: Optional[List[Dict[str, Any]]] = Field(None, description="声纹列表")
    error: Optional[str] = Field(None, description="错误信息")


class WebSocketMessage(BaseModel):
    """WebSocket消息模型"""
    action: str = Field(..., description="操作类型")
    data: Dict[str, Any] = Field(..., description="消息数据")
