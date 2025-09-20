# GPT_SoVITS package initialization

# Import submodules with short aliases for simplified path management
# Note: Removed top-level submodule imports to avoid circular imports
# from . import module, text, AR, feature_extractor, TTS_infer_pack

# Re-export module components
from .module.transforms import piecewise_rational_quadratic_transform
from .module.commons import init_weights, get_padding
from .module.mrte_model import MRTE
from .module.quantize import ResidualVectorQuantizer
from .module.models import SynthesizerTrn, SynthesizerTrnV3, Generator
from .module.mel_processing import mel_spectrogram_torch, spectrogram_torch

# Re-export text components
from .text.symbols import punctuation
from .text.cleaner import clean_text
from .text import cleaned_text_to_sequence

# Re-export other components
from .AR.models.t2s_lightning_module import Text2SemanticLightningModule
from .feature_extractor.cnhubert import CNHubert
from . import process_ckpt
from .process_ckpt import get_sovits_version_from_path_fast, load_sovits_new
from .TTS_infer_pack.text_segmentation_method import splits, split_big_text, get_method as get_seg_method
from .TTS_infer_pack.TextPreprocessor import TextPreprocessor

# Re-export f5_tts if needed
try:
    from .f5_tts.model import DiT
    _DIT_AVAILABLE = True
except ImportError:
    _DIT_AVAILABLE = False
    DiT = None

__all__ = [
    'piecewise_rational_quadratic_transform',
    'init_weights', 'get_padding', 'MRTE', 'ResidualVectorQuantizer',
    'SynthesizerTrn', 'SynthesizerTrnV3', 'Generator',
    'mel_spectrogram_torch', 'spectrogram_torch',
    'punctuation',
    'clean_text', 'cleaned_text_to_sequence',
    'Text2SemanticLightningModule', 'CNHubert',
    'process_ckpt', 'get_sovits_version_from_path_fast', 'load_sovits_new',
    'splits', 'TextPreprocessor', 'DiT', 'split_big_text', 'get_seg_method'
]