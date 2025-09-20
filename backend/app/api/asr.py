"""
语音识别API路由
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from ..core.stt_security import verify_api_key
from ..models.stt_schemas import AudioRecognitionRequest, AudioRecognitionResponse
from ..services.asr_service import get_asr_service
from ..services.vpr_service import get_vpr_service

# 配置日志
logger = logging.getLogger("asr_api")

# 创建路由
router = APIRouter(prefix="/asr", tags=["语音识别"])


@router.post("/recognize", response_model=AudioRecognitionResponse, summary="语音识别")
async def recognize_audio(
    request: AudioRecognitionRequest,
    authenticated: bool = Depends(verify_api_key)
) -> Dict[str, Any]:
    """
    识别音频并返回文本结果
    
    - **audio_data**: Base64编码的音频数据
    - **check_voiceprint**: 是否执行声纹检查
    - **only_register_user**: 是否仅识别已注册用户
    - **identify_unregistered**: 是否识别未注册用户的语音
    
    返回:
    - **success**: 是否成功
    - **text**: 识别的文本
    - **user_id**: 用户ID (如果进行了声纹识别)
    - **user_name**: 用户名称 (如果进行了声纹识别)
    - **similarity**: 声纹相似度 (如果进行了声纹识别)
    - **error**: 错误信息 (如果失败)
    """
    # 获取服务实例
    asr_service = get_asr_service()
    vpr_service = get_vpr_service()
    
    # 解码音频数据
    audio_data = asr_service.decode_audio(request.audio_data)
    if not audio_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的音频数据"
        )
    
    # 如果需要执行声纹检查
    user_info = {}
    if request.check_voiceprint:
        # 识别声纹
        vpr_result = vpr_service.identify_voiceprint(audio_data)
        
        if vpr_result["success"]:
            user_info = {
                "user_id": vpr_result["user_id"],
                "user_name": vpr_result["user_name"],
                "similarity": vpr_result["similarity"]
            }
        elif request.only_register_user:
            # 如果只识别已注册用户且声纹识别失败，则直接返回
            return {
                "success": False,
                "error": "未识别到已注册用户的声纹"
            }
    
    # 如果不需要声纹检查，或者声纹检查通过，或者允许识别未注册用户
    if not request.check_voiceprint or user_info or request.identify_unregistered:
        # 执行语音识别
        result = asr_service.recognize(audio_data)
        
        if result["success"]:
            return {
                "success": True,
                "text": result["text"],
                **user_info
            }
        else:
            return {
                "success": False,
                "error": result["error"]
            }
    
    # 默认情况
    return {
        "success": False,
        "error": "未能识别语音"
    }
