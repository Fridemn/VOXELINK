# app/api 包初始化

from .asr import router as asr_router
from .vpr import router as vpr_router
from .ws import router as ws_router
from .system import api_system
from .llm import api_llm

__all__ = [
    "asr_router",
    "vpr_router", 
    "ws_router",
    "api_system",
    "api_llm"
]
