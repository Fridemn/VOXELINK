"""
安全模块 - 提供API认证和授权功能
"""

from fastapi import Security, HTTPException, Depends, status
from fastapi.security.api_key import APIKeyHeader
from typing import Optional

from .stt_config import get_settings

# API密钥头
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key_header: str = Security(API_KEY_HEADER)) -> Optional[str]:
    """获取API密钥
    
    Args:
        api_key_header: API密钥头
        
    Returns:
        API密钥
    """
    return api_key_header


async def verify_api_key(api_key: str = Depends(get_api_key)) -> bool:
    """验证API密钥
    
    Args:
        api_key: API密钥
        
    Returns:
        如果验证通过，返回True
        
    Raises:
        HTTPException: 如果验证失败
    """
    settings = get_settings()
    
    # 如果不需要认证，直接返回True
    if not settings.get("require_auth", False):
        return True
    
    # 验证API密钥
    if not api_key or api_key != settings.get("api_key", ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的API密钥",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return True
