#!/usr/bin/env python3
"""
GPT-SoVITS FastAPI 服务器主入口
简化的主入口，只用于导入路由和启动服务器
"""

import logging
import uvicorn

# 导入应用和路由模块
from app import app, config
from router import router, set_config

# 配置日志
logger = logging.getLogger(__name__)

# 设置路由模块的配置
set_config(config)

# 包含路由
app.include_router(router)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GPT-SoVITS FastAPI Server")
    parser.add_argument("--host", default=None, help="Host to bind to")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    
    args = parser.parse_args()
    
    # 使用配置文件中的服务器设置，命令行参数优先
    server_config = config.get("server", {})
    host = args.host or server_config.get("host", "127.0.0.1")
    port = args.port or server_config.get("port", 9880)
    log_level = server_config.get("log_level", "info")
    
    logger.info(f"启动 GPT-SoVITS FastAPI 服务器")
    logger.info(f"访问地址: http://{host}:{port}")
    logger.info(f"API 文档: http://{host}:{port}/docs")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        workers=args.workers,
        log_level=log_level
    )