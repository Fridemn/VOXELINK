import uvicorn
import argparse
import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise
from loguru import logger

# 添加GPT_SoVITS路径到sys.path
gpt_path = os.path.join(os.path.dirname(__file__), "GPT_SoVITS")
if gpt_path not in sys.path:
    sys.path.insert(0, gpt_path)

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
            # 导入STT API路由
            from app.api import asr_router, vpr_router, ws_router
            app.include_router(asr_router, prefix="/stt")
            app.include_router(vpr_router, prefix="/stt")
            app.include_router(ws_router, prefix="/stt")
            logger.info("STT服务已启用")
        except Exception as e:
            logger.warning(f"无法加载STT模块: {e}")
            import traceback
            logger.warning(traceback.format_exc())

    # 条件注册TTS路由
    if enable_tts:
        try:
            # 添加GSVI路径到sys.path
            tts_path = os.path.join(os.path.dirname(__file__), "app", "core", "tts")
            if tts_path not in sys.path:
                sys.path.insert(0, tts_path)
            
            # 添加GPT_SoVITS路径到sys.path
            gpt_path = os.path.join(os.path.dirname(__file__), "GPT_SoVITS")
            if gpt_path not in sys.path:
                sys.path.insert(0, gpt_path)
            
            # 临时修改当前工作目录，以便相对导入正常工作
            original_cwd = os.getcwd()
            os.chdir(tts_path)
            
            try:
                # 动态导入TTS路由模块
                import importlib.util
                spec = importlib.util.spec_from_file_location("router", os.path.join(tts_path, "router.py"))
                router_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(router_module)
                
                # 加载GSVI配置
                def load_tts_config():
                    """加载GSVI配置文件"""
                    config_path = os.path.join(tts_path, "config.json")
                    default_config = {
                        "default_models": {
                            "sovits_path": "GPT_SoVITS/models/SoVITS_weights_v4/March7_e10_s4750_l32.pth",
                            "gpt_path": "GPT_SoVITS/models/GPT_weights_v4/March7-e15.ckpt"
                        },
                        "server": {
                            "host": "0.0.0.0",
                            "port": 9880,
                            "log_level": "info"
                        },
                        "inference": {
                            "default_language": "chinese",
                            "default_how_to_cut": "no_cut",
                            "default_top_k": 15,
                            "default_top_p": 1.0,
                            "default_temperature": 1.0,
                            "default_ref_free": False,
                            "default_speed": 1.0,
                            "default_if_freeze": False,
                            "default_sample_steps": 8,
                            "default_if_sr": False,
                            "default_pause_second": 0.3
                        }
                    }
                    
                    if os.path.exists(config_path):
                        try:
                            import json
                            with open(config_path, 'r', encoding='utf-8') as f:
                                config = json.load(f)
                            logger.info(f"GSVI配置文件加载成功: {config_path}")
                            return config
                        except Exception as e:
                            logger.warning(f"GSVI配置文件加载失败，使用默认配置: {e}")
                            return default_config
                    else:
                        # 创建默认配置文件
                        try:
                            import json
                            with open(config_path, 'w', encoding='utf-8') as f:
                                json.dump(default_config, f, ensure_ascii=False, indent=2)
                            logger.info(f"创建默认GSVI配置文件: {config_path}")
                        except Exception as e:
                            logger.warning(f"无法创建GSVI配置文件: {e}")
                        return default_config
                
                tts_config = load_tts_config()
                
                # 设置路由模块的配置
                router_module.set_config(tts_config)
                
                # 设置TTS服务的配置
                try:
                    from app.core.tts.tts_service import set_tts_config
                    set_tts_config(tts_config)
                except ImportError as e:
                    logger.warning(f"无法设置TTS服务配置: {e}")
                
                # 包含TTS路由到主应用
                app.include_router(router_module.router, prefix="/tts", tags=["语音合成接口"])
                
                logger.info("TTS (GSVI) 服务已启用")
            finally:
                # 恢复原始工作目录
                os.chdir(original_cwd)
                
        except Exception as e:
            logger.warning(f"无法加载TTS模块: {e}")
            import traceback
            logger.warning(traceback.format_exc())

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
