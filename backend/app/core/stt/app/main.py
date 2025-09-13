"""
FastAPI版本的语音识别服务入口

这个模块使用FastAPI框架重构了原有的WebSocket服务器，提供相同的功能但使用现代化的API框架。
"""

import logging
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.api import api_router
from app.core.config import get_settings
from app.services.asr_service import get_asr_service
from app.services.vpr_service import get_vpr_service

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("app")

# 获取配置
settings = get_settings()

# 创建应用
app = FastAPI(
    title="语音识别WebSocket服务",
    description="提供实时语音识别和声纹识别功能",
    version="1.0.0",
    swagger_ui_parameters={
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True
    }
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

# 配置OpenAPI标签
app.openapi_tags = [
    {"name": "语音识别", "description": "语音识别相关API"},
    {"name": "声纹识别", "description": "声纹识别相关API"},
    {"name": "WebSocket", "description": "WebSocket接口"},
]

# 包含API路由
app.include_router(api_router)

# 挂载静态文件目录
try:
    static_dir = Path(__file__).parent.parent / "static"
    if not static_dir.exists():
        static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
except Exception as e:
    logger.warning(f"挂载静态文件目录失败: {e}")


@app.on_event("startup")
async def startup_event():
    """应用启动事件，预加载服务"""
    logger.info("服务启动中，预加载模型...")
    # 预加载模型，避免第一次请求时的延迟
    asr_service = get_asr_service()
    vpr_service = get_vpr_service()
    logger.info("模型预加载完成")


@app.get("/", tags=["默认"])
async def root():
    """
    根路径，返回服务状态
    """
    return {
        "status": "running",
        "service": "语音识别WebSocket服务",
        "version": "1.0.0"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理
    """
    logger.error(f"全局异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误: {str(exc)}"},
    )


def start():
    """启动服务"""
    host = settings.get("host", "0.0.0.0")
    port = settings.get("port", 8765)
    
    # 启动服务
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    start()
