"""
声纹识别API路由
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List

from ..models.stt_schemas import (
    VoiceprintRegistrationRequest, VoiceprintRegistrationResponse,
    VoiceprintCompareRequest, VoiceprintCompareResponse,
    VoiceprintMatchRequest, VoiceprintMatchResponse,
    VoiceprintRemoveRequest, VoiceprintRemoveResponse,
    VoiceprintListResponse
)
from ..services.vpr_service import get_vpr_service

# 配置日志
logger = logging.getLogger("vpr_api")

# 创建路由
router = APIRouter(prefix="/vpr", tags=["声纹识别"])


@router.post("/register", response_model=VoiceprintRegistrationResponse, summary="注册声纹")
async def register_voiceprint(
    request: VoiceprintRegistrationRequest
) -> Dict[str, Any]:
    """
    注册新的声纹样本
    
    - **audio_data**: Base64编码的音频数据
    - **user_id**: 用户ID
    - **user_name**: 用户名称 (可选)
    
    返回:
    - **success**: 是否成功
    - **message**: 成功信息 (如果成功)
    - **user_id**: 用户ID (如果成功)
    - **user_name**: 用户名称 (如果成功)
    - **error**: 错误信息 (如果失败)
    """
    # 获取服务实例
    vpr_service = get_vpr_service()
    
    # 解码音频数据
    audio_data = vpr_service.decode_audio(request.audio_data)
    if not audio_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的音频数据"
        )
    
    # 注册声纹
    result = vpr_service.register_voiceprint(
        request.user_id,
        request.user_name or "未命名用户",
        audio_data
    )
    
    return result


@router.post("/compare", response_model=VoiceprintCompareResponse, summary="比对声纹")
async def compare_voiceprints(
    request: VoiceprintCompareRequest
) -> Dict[str, Any]:
    """
    比对两段音频的声纹相似度
    
    - **audio_data1**: Base64编码的第一段音频数据
    - **audio_data2**: Base64编码的第二段音频数据
    
    返回:
    - **success**: 是否成功
    - **similarity**: 相似度 (如果成功)
    - **is_same_person**: 是否为同一人 (如果成功)
    - **error**: 错误信息 (如果失败)
    """
    # 获取服务实例
    vpr_service = get_vpr_service()
    
    # 解码音频数据
    audio_data1 = vpr_service.decode_audio(request.audio_data1)
    audio_data2 = vpr_service.decode_audio(request.audio_data2)
    
    if not audio_data1 or not audio_data2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的音频数据"
        )
    
    # 比对声纹
    result = vpr_service.compare_voiceprints(audio_data1, audio_data2)
    
    return result


@router.post("/identify", response_model=VoiceprintMatchResponse, summary="识别声纹")
async def identify_voiceprint(
    request: VoiceprintMatchRequest
) -> Dict[str, Any]:
    """
    识别音频的声纹
    
    - **audio_data**: Base64编码的音频数据
    
    返回:
    - **success**: 是否成功
    - **user_id**: 用户ID (如果成功)
    - **user_name**: 用户名称 (如果成功)
    - **similarity**: 相似度 (如果成功)
    - **error**: 错误信息 (如果失败)
    """
    # 获取服务实例
    vpr_service = get_vpr_service()
    
    # 解码音频数据
    audio_data = vpr_service.decode_audio(request.audio_data)
    if not audio_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的音频数据"
        )
    
    # 识别声纹
    result = vpr_service.identify_voiceprint(audio_data)
    
    return result


@router.post("/remove", response_model=VoiceprintRemoveResponse, summary="删除声纹")
async def remove_voiceprint(
    request: VoiceprintRemoveRequest
) -> Dict[str, Any]:
    """
    删除声纹
    
    - **user_id**: 用户ID
    
    返回:
    - **success**: 是否成功
    - **message**: 成功信息 (如果成功)
    - **error**: 错误信息 (如果失败)
    """
    # 获取服务实例
    vpr_service = get_vpr_service()
    
    # 删除声纹
    result = vpr_service.remove_voiceprint(request.user_id)
    
    return result


@router.get("/list", response_model=VoiceprintListResponse, summary="获取声纹列表")
async def list_voiceprints() -> Dict[str, Any]:
    """
    获取声纹列表
    
    返回:
    - **success**: 是否成功
    - **voiceprints**: 声纹列表 (如果成功)
    - **error**: 错误信息 (如果失败)
    """
    # 获取服务实例
    vpr_service = get_vpr_service()
    
    # 获取声纹列表
    result = vpr_service.list_voiceprints()
    
    return result
