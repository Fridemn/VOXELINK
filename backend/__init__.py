"""
VOXELINK Backend Package

This module provides convenient aliases for deep imports to simplify path management.
Similar to Node.js path mapping (@/), we use short aliases to reduce import verbosity.

Usage:
    from backend import core, models, services, utils
"""

# Import app module and its components
from . import app

from .app import core, models, utils, config, api
from .app.core import pipeline, db, llm, tts
from .app.core.tts.tts_service import set_tts_config
from .app.core.llm.chat import LLMMessage, LLMResponse, LLMConfig, BaseLLM, OpenAILLM, OllamaLLM
from .app.core.llm.message import Message, Response, MessageRole, MessageSender, MessageComponent
from .app.core.db.db_history import db_message_history
from .app.models import user, chat, stt
from .app.utils import logger
from .app.config import app_config
from .app.api.system import api_system
from .app.api.llm import api_llm
from .app.api.asr import router as asr
from .app.api.vpr import router as vpr
from .app.api.ws import router as ws
from .app.models import response

__all__ = [
    'app',
    'core', 'models', 'services', 'utils', 'config', 'api',
    'pipeline', 'db', 'llm', 'tts','set_tts_config', 'db_message_history',
    'Message', 'Response', 'MessageRole', 'MessageSender', 'MessageComponent',
    'LLMMessage', 'LLMResponse', 'LLMConfig', 'BaseLLM', 'OpenAILLM', 'OllamaLLM',
    'user', 'chat', 'stt',
    'asr_service', 'llm_service', 'vpr_service',
    'logger',
    'app_config',
    'api_system', 'api_llm', 'asr', 'vpr', 'ws',
    'response'
]