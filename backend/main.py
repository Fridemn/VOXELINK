import uvicorn
import argparse
import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise
from loguru import logger

from app import app_config
from app.api.system import api_system
from app.api.llm import api_llm
from fastapi.staticfiles import StaticFiles

# 解析命令行参数
parser = argparse.ArgumentParser(description="VOXELINK Backend Server")
parser.add_argument("--enable-stt", action="store_true", help="Enable STT (Speech-to-Text) service")
parser.add_argument("--enable-tts", action="store_true", help="Enable TTS (Text-to-Speech) service")
parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

def create_app(enable_stt: bool = False, enable_tts: bool = False):
    """创建FastAPI应用"""
    
    app = FastAPI(title="VOXELINK Backend", description="Voxelink Backend with integrated STT/TTS", version="0.1.0")

    # 注册 SQLite + Tortoise ORM 服务
    register_tortoise(
        app,
        db_url="sqlite://db.sqlite3",
        modules={"models": ["app.models"]},
        generate_schemas=True,
        add_exception_handlers=True,
    )

    # 注册根路由
    @app.get("/")
    async def root():
        """根路由，返回状态消息"""
        services = ["backend"]
        if enable_stt:
            services.append("stt")
        if enable_tts:
            services.append("tts")
        return {
            "message": "okay",
            "services": services,
            "version": "0.1.0"
        }

    # 注册 CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册各部分的 API 路由
    app.include_router(api_system, prefix="/system", tags=["系统相关接口"])
    app.include_router(api_llm, prefix="/llm", tags=["大语言模型相关接口"])

    # 条件注册STT路由
    if enable_stt:
        try:
            # 添加STT模块路径到sys.path
            stt_app_path = os.path.join(os.path.dirname(__file__), "app", "core", "stt", "app")
            if stt_app_path not in sys.path:
                sys.path.insert(0, stt_app_path)
            
            # 临时修改当前工作目录，以便相对导入正常工作
            original_cwd = os.getcwd()
            os.chdir(stt_app_path)
            
            try:
                # 导入STT API路由
                from api import api_router as stt_api_router
                app.include_router(stt_api_router, prefix="/stt", tags=["语音识别接口"])
                logger.info("STT服务已启用")
            finally:
                # 恢复原始工作目录
                os.chdir(original_cwd)
                
        except Exception as e:
            logger.warning(f"无法加载STT模块: {e}")
            import traceback
            logger.warning(traceback.format_exc())

    # 条件注册TTS路由
    if enable_tts:
        try:
            # 添加GSVI路径到sys.path
            gsvi_path = os.path.join(os.path.dirname(__file__), "app", "core", "gsvi")
            if gsvi_path not in sys.path:
                sys.path.insert(0, gsvi_path)
            
            # 动态导入TTS模块
            import importlib.util
            spec = importlib.util.spec_from_file_location("api_server", os.path.join(gsvi_path, "api_server.py"))
            tts_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tts_module)
            
            # 获取TTS应用
            tts_app = tts_module.app
            
            # 将TTS应用的路由注册到主应用
            for route in tts_app.routes:
                if hasattr(route, 'path') and hasattr(route, 'methods') and hasattr(route, 'endpoint'):
                    # 重新注册路由到主应用，添加前缀
                    app.add_api_route(
                        path=f"/tts{route.path}",
                        endpoint=route.endpoint,
                        methods=route.methods,
                        name=f"tts_{route.name}" if hasattr(route, 'name') and route.name else None,
                        tags=["语音合成接口"]
                    )
            
            logger.info("TTS服务已启用")
        except Exception as e:
            logger.warning(f"无法加载TTS模块: {e}")

    # 注册静态资源目录
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    return app

# 创建默认应用实例（仅在直接运行时创建）
if __name__ != "__main__":
    # 当作为模块导入时，不创建应用实例
    app = None
else:
    # 当直接运行时创建应用实例
    app = create_app()

if __name__ == "__main__":
    # 解析命令行参数
    args = parser.parse_args()
    
    # 使用参数重新创建应用
    app = create_app(enable_stt=args.enable_stt, enable_tts=args.enable_tts)
    
    logger.info("App正在运行")
    if args.enable_stt:
        logger.info("STT服务已启用")
    if args.enable_tts:
        logger.info("TTS服务已启用")
    
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
