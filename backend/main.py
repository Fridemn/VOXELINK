import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise
from loguru import logger

from app import app_config
from app.api.system import api_system
from app.api.llm import api_llm
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="API", description="Voxelink Backend", version="0.1.0")

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
    return {"message": "okay"}


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

# 注册静态资源目录
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    logger.info("App正在运行")
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
