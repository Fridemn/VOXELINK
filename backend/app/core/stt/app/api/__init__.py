"""
API路由初始化
"""

from fastapi import APIRouter
from app.api import asr, vpr, ws

# 创建API路由器
api_router = APIRouter()

# 包含其他路由
api_router.include_router(asr.router)
api_router.include_router(vpr.router)
api_router.include_router(ws.router)