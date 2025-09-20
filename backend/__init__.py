"""
VOXELINK Backend Package

This module provides convenient aliases for deep imports to simplify path management.
Similar to Node.js path mapping (@/), we use short aliases to reduce import verbosity.

Usage:
    from backend import core, models, services, utils
    # Instead of: from app.core.stt_config import get_settings
    # Use: from core.stt_config import get_settings
"""

# Import app module and its components
from . import app

# Re-export app's components with short aliases
from .app import core, models, utils, config, api, schemas
# Note: services import removed to avoid circular import
from .app.core import pipeline, db, funcall, llm, tts
from .app.core.funcall.tool_functions import get_available_functions, execute_function, get_function_need_llm, find_function_by_command
from .app.core.funcall.source import BaseFunction
from .app.core.funcall.source.date_functions import CurrentDateFunction, DateDifferenceFunction
from .app.core.funcall.source.test_functions import TestFunction
from .app.core.tts.tts_service import set_tts_config
from .app.core.llm.chat import LLMMessage, LLMResponse, LLMConfig, BaseLLM, OpenAILLM, AnthropicLLM, OllamaLLM
from .app.core.llm.message import Message, Response, MessageRole, MessageSender, MessageComponent, MessageType
from .app.core.stt_config import get_settings
from .app.core.db.db_history import db_message_history
from .app.models import user, chat, stt_schemas
# Note: services import removed to avoid circular import
from .app.utils import logger, token_counter
from .app.config import app_config
from .app.api.system import api_system
from .app.api.llm import api_llm
from .app.api.asr import router as asr
from .app.api.vpr import router as vpr
from .app.api.ws import router as ws
from .app.schemas import response

__all__ = [
    'app',
    'core', 'models', 'services', 'utils', 'config', 'api', 'schemas',
    'pipeline', 'db', 'funcall', 'llm', 'tts', 'get_settings',     'set_tts_config', 'db_message_history',
    'BaseFunction', 'CurrentDateFunction', 'DateDifferenceFunction', 'TestFunction',
    'tool_functions',
    'get_available_functions', 'execute_function', 'get_function_need_llm', 'find_function_by_command',
    'Message', 'Response', 'MessageRole', 'MessageSender', 'MessageComponent', 'MessageType',
    'LLMMessage', 'LLMResponse', 'LLMConfig', 'BaseLLM', 'OpenAILLM', 'AnthropicLLM', 'OllamaLLM',
    'user', 'chat', 'stt_schemas',
    'asr_service', 'llm_service', 'vpr_service',
    'logger', 'token_counter',
    'app_config',
    'api_system', 'api_llm', 'asr', 'vpr', 'ws',
    'response'
]