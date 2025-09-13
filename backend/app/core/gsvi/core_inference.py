"""
Core inference module for GPT-SoVITS without Gfrom AR.models.t2s_lightning_module import Text2SemanticLightningModule
from feature_extractor import cnhubert
from module.mel_processing import spectrogram_torch, mel_spectrogram_torch
from module.models import SynthesizerTrn, SynthesizerTrnV3, Generator
from process_ckpt import get_sovits_version_from_path_fast, load_sovits_new
from text import cleaned_text_to_sequence
from text.cleaner import clean_text
from transformers import AutoModelForMaskedLM, AutoTokenizer
from torchaudio.transforms import Resample
try:
    from BigVGAN.bigvgan import BigVGAN
except ImportError:
    BigVGAN = None
try:
    from tools.audio_sr import AP_BWE
except ImportError:
    AP_BWE = Nonependencies
"""

import logging
import os
import re
import sys
import warnings
from time import time as ttime

import numpy as np
import torch
import torchaudio
import librosa
import random

logging.getLogger("markdown_it").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("charset_normalizer").setLevel(logging.ERROR)
logging.getLogger("torchaudio._extension").setLevel(logging.ERROR)
logging.getLogger("multipart.multipart").setLevel(logging.ERROR)
warnings.simplefilter(action="ignore", category=FutureWarning)

# Import necessary components from GPT_SoVITS
now_dir = os.getcwd()
sys.path.append(now_dir)
sys.path.append("%s/GPT_SoVITS" % (now_dir))

# Set up paths
version = os.environ.get("version", "v2")
cnhubert_base_path = os.environ.get("cnhubert_base_path", "GPT_SoVITS/pretrained_models/chinese-hubert-base")
bert_path = os.environ.get("bert_path", "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large")

# Check CUDA availability and set device
if "_CUDA_VISIBLE_DEVICES" in os.environ:
    os.environ["CUDA_VISIBLE_DEVICES"] = os.environ["_CUDA_VISIBLE_DEVICES"]
is_half = eval(os.environ.get("is_half", "True")) and torch.cuda.is_available()

if torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"

# Import after setting paths
from AR.models.t2s_lightning_module import Text2SemanticLightningModule
from feature_extractor import cnhubert
from module.mel_processing import spectrogram_torch, mel_spectrogram_torch
from module.models import SynthesizerTrn, SynthesizerTrnV3, Generator
from process_ckpt import get_sovits_version_from_path_fast, load_sovits_new
from text import cleaned_text_to_sequence
from text.cleaner import clean_text
from transformers import AutoModelForMaskedLM, AutoTokenizer

# Set cnhubert path
cnhubert.cnhubert_base_path = cnhubert_base_path

# Global model variables
dtype = torch.float16 if is_half else torch.float32
model_version = "v2"

# Model instances
t2s_model = None
vq_model = None
ssl_model = None
hps = None
hz = 50
max_sec = 10
cache = {}
bert_model = None
tokenizer = None
hifigan_model = None
bigvgan_model = None
sr_model = None

# 添加重采样变换字典
resample_transform_dict = {}

# Model version sets
v3v4set = {"v3", "v4"}

# Load default model paths
pretrained_sovits_name = [
    "GPT_SoVITS/pretrained_models/s2G488k.pth",
    "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s2G2333k.pth",
    "GPT_SoVITS/pretrained_models/s2Gv3.pth",
    "GPT_SoVITS/pretrained_models/gsv-v4-pretrained/s2Gv4.pth",
]
pretrained_gpt_name = [
    "GPT_SoVITS/pretrained_models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt",
    "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
    "GPT_SoVITS/pretrained_models/s1v3.ckpt",
    "GPT_SoVITS/pretrained_models/s1v3.ckpt",
]

# 路径将由外部设置，这里只提供默认值
gpt_path = os.environ.get("GPT_PATH", "GPT_weights_v4/March7-e15.ckpt")
sovits_path = os.environ.get("SOVITS_PATH", "SoVITS_weights_v4/March7_e10_s4750_l32.pth")
vocoder_path = os.environ.get("VOCODER_PATH", f"{now_dir}/GPT_SoVITS/pretrained_models/gsv-v4-pretrained/vocoder.pth")

# Language mappings
dict_language_v1 = {
    "中文": "all_zh",
    "英文": "en", 
    "日文": "all_ja",
    "中英混合": "zh",
    "日英混合": "ja",
    "多语种混合": "auto",
}

dict_language_v2 = {
    "中文": "all_zh",
    "英文": "en",
    "日文": "all_ja",
    "粤语": "all_yue",
    "韩文": "all_ko",
    "中英混合": "zh",
    "日英混合": "ja",
    "粤英混合": "yue",
    "韩英混合": "ko",
    "多语种混合": "auto",
    "多语种混合(粤语)": "auto_yue",
}

dict_language = dict_language_v1 if version == "v1" else dict_language_v2

# Initialize splits for text processing
splits = {"，", "。", "？", "！", ",", ".", "?", "!", "~", ":", "：", "—", "…", }

def i18n(key):
    """Simple i18n function"""
    return key

class DictToAttrRecursive(dict):
    def __init__(self, input_dict):
        super().__init__(input_dict)
        for key, value in input_dict.items():
            if isinstance(value, dict):
                value = DictToAttrRecursive(value)
            self[key] = value
            setattr(self, key, value)

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(f"Attribute {item} not found")

    def __setattr__(self, key, value):
        if isinstance(value, dict):
            value = DictToAttrRecursive(value)
        super(DictToAttrRecursive, self).__setitem__(key, value)
        super().__setattr__(key, value)

    def __delattr__(self, item):
        try:
            del self[item]
        except KeyError:
            raise AttributeError(f"Attribute {item} not found")

def set_seed(seed):
    if seed == -1:
        seed = random.randint(0, 1000000)
    seed = int(seed)
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)

def init_models():
    """Initialize BERT and SSL models"""
    global bert_model, tokenizer, ssl_model
    
    # Initialize BERT
    tokenizer = AutoTokenizer.from_pretrained(bert_path)
    bert_model = AutoModelForMaskedLM.from_pretrained(bert_path)
    if is_half:
        bert_model = bert_model.half().to(device)
    else:
        bert_model = bert_model.to(device)
    
    # Initialize SSL model
    ssl_model = cnhubert.get_model()
    if is_half:
        ssl_model = ssl_model.half().to(device)
    else:
        ssl_model = ssl_model.to(device)

def get_bert_feature(text, word2ph):
    """Extract BERT features"""
    with torch.no_grad():
        inputs = tokenizer(text, return_tensors="pt")
        for i in inputs:
            inputs[i] = inputs[i].to(device)
        res = bert_model(**inputs, output_hidden_states=True)
        res = torch.cat(res["hidden_states"][-3:-2], -1)[0].cpu()[1:-1]
    assert len(word2ph) == len(text)
    phone_level_feature = []
    for i in range(len(word2ph)):
        repeat_feature = res[i].repeat(word2ph[i], 1)
        phone_level_feature.append(repeat_feature)
    phone_level_feature = torch.cat(phone_level_feature, dim=0)
    return phone_level_feature.T

def clean_text_inf(text, language, version):
    """Clean text with language processing"""
    language = language.replace("all_", "")
    phones, word2ph, norm_text = clean_text(text, language, version)
    phones = cleaned_text_to_sequence(phones, version)
    return phones, word2ph, norm_text

def get_bert_inf(phones, word2ph, norm_text, language):
    """Get BERT features with language handling"""
    language = language.replace("all_", "")
    if language == "zh":
        bert = get_bert_feature(norm_text, word2ph).to(device)
    else:
        bert = torch.zeros(
            (1024, len(phones)),
            dtype=torch.float16 if is_half else torch.float32,
        ).to(device)
    return bert

def get_phones_and_bert(text, language, version, final=False):
    """Extract phones and bert features from text - based on inference_webui.py"""
    try:
        from text.LangSegmenter import LangSegmenter
        from text import chinese
    except ImportError:
        # Fallback if LangSegmenter is not available
        phones, word2ph, norm_text = clean_text_inf(text, language, version)
        if language.replace("all_", "") == "zh":
            bert = get_bert_feature(norm_text, word2ph).to(device).to(dtype)
        else:
            bert = torch.zeros(
                (1024, len(phones)),
                dtype=dtype,
            ).to(device)
        return phones, bert, norm_text
    
    if language in {"en", "all_zh", "all_ja", "all_ko", "all_yue"}:
        formattext = text
        while "  " in formattext:
            formattext = formattext.replace("  ", " ")
        if language == "all_zh":
            if re.search(r"[A-Za-z]", formattext):
                formattext = re.sub(r"[a-z]", lambda x: x.group(0).upper(), formattext)
                formattext = chinese.mix_text_normalize(formattext)
                return get_phones_and_bert(formattext, "zh", version)
            else:
                phones, word2ph, norm_text = clean_text_inf(formattext, language, version)
                bert = get_bert_feature(norm_text, word2ph).to(device)
        elif language == "all_yue" and re.search(r"[A-Za-z]", formattext):
            formattext = re.sub(r"[a-z]", lambda x: x.group(0).upper(), formattext)
            formattext = chinese.mix_text_normalize(formattext)
            return get_phones_and_bert(formattext, "yue", version)
        else:
            phones, word2ph, norm_text = clean_text_inf(formattext, language, version)
            bert = torch.zeros(
                (1024, len(phones)),
                dtype=torch.float16 if is_half else torch.float32,
            ).to(device)
    elif language in {"zh", "ja", "ko", "yue", "auto", "auto_yue"}:
        textlist = []
        langlist = []
        if language == "auto":
            for tmp in LangSegmenter.getTexts(text):
                langlist.append(tmp["lang"])
                textlist.append(tmp["text"])
        elif language == "auto_yue":
            for tmp in LangSegmenter.getTexts(text):
                if tmp["lang"] == "zh":
                    tmp["lang"] = "yue"
                langlist.append(tmp["lang"])
                textlist.append(tmp["text"])
        else:
            for tmp in LangSegmenter.getTexts(text):
                if tmp["lang"] == "en":
                    langlist.append(tmp["lang"])
                else:
                    langlist.append(language)
                textlist.append(tmp["text"])
        
        phones_list = []
        bert_list = []
        norm_text_list = []
        for i in range(len(textlist)):
            lang = langlist[i]
            phones, word2ph, norm_text = clean_text_inf(textlist[i], lang, version)
            bert = get_bert_inf(phones, word2ph, norm_text, lang)
            phones_list.append(phones)
            norm_text_list.append(norm_text)
            bert_list.append(bert)
        bert = torch.cat(bert_list, dim=1)
        phones = sum(phones_list, [])
        norm_text = "".join(norm_text_list)

    if not final and len(phones) < 6:
        return get_phones_and_bert("." + text, language, version, final=True)

    return phones, bert.to(dtype), norm_text

def get_specc(hps, ref_wav_path):
    """Get spectrogram from reference audio"""
    audio, sr = librosa.load(ref_wav_path, sr=hps.data.sampling_rate)
    audio = torch.FloatTensor(audio)
    audio_norm = audio.unsqueeze(0)
    spec = spectrogram_torch(
        audio_norm,
        hps.data.filter_length,
        hps.data.sampling_rate,
        hps.data.hop_length,
        hps.data.win_length,
        center=False,
    )
    return spec

def load_models_from_paths(gpt_path, sovits_path):
    """Load T2S and SoVITS models from file paths"""
    global t2s_model, vq_model, hps, hz, max_sec, model_version
    
    # Load T2S model
    dict_s1 = torch.load(gpt_path, map_location=device)
    config = dict_s1["config"]
    max_sec = config["data"]["max_sec"]
    t2s_model = Text2SemanticLightningModule(config, "****", is_train=False)
    t2s_model.load_state_dict(dict_s1["weight"])
    t2s_model = t2s_model.to(device).eval()
    if is_half:
        t2s_model = t2s_model.half()
    
    # Load SoVITS model
    version_info, model_version, if_lora_v3 = get_sovits_version_from_path_fast(sovits_path)
    dict_s2 = load_sovits_new(sovits_path)
    hps = dict_s2["config"]
    hps = DictToAttrRecursive(hps)
    hps.model.semantic_frame_rate = "25hz"
    
    if model_version not in {"v3", "v4"}:
        vq_model = SynthesizerTrn(
            hps.data.filter_length // 2 + 1,
            hps.train.segment_size // hps.data.hop_length,
            **hps.model
        )
    else:
        vq_model = SynthesizerTrnV3(
            hps.data.filter_length // 2 + 1,
            hps.train.segment_size // hps.data.hop_length,
            **hps.model
        )
    
    vq_model.load_state_dict(dict_s2["weight"], strict=False)
    vq_model = vq_model.to(device).eval()
    if is_half:
        vq_model = vq_model.half()

def change_sovits_weights(sovits_path):
    """Change SoVITS model weights - 使用与inference_webui.py相同的实现"""
    global vq_model, hps, version, model_version, dict_language, if_lora_v3
    
    try:
        from peft import LoraConfig, get_peft_model
        from process_ckpt import load_sovits_new
        
        version_info, model_version, if_lora_v3 = get_sovits_version_from_path_fast(sovits_path)
        print(f"Loading SoVITS model: {sovits_path}, version: {version_info}, model_version: {model_version}, lora: {if_lora_v3}")
        
        # 检查v3/v4底模是否存在
        path_sovits_v3 = "GPT_SoVITS/pretrained_models/s2Gv3.pth"
        path_sovits_v4 = "GPT_SoVITS/pretrained_models/gsv-v4-pretrained/s2Gv4.pth"
        is_exist_s2gv3 = os.path.exists(path_sovits_v3)
        is_exist_s2gv4 = os.path.exists(path_sovits_v4)
        is_exist = is_exist_s2gv3 if model_version == "v3" else is_exist_s2gv4
        
        if if_lora_v3 == True and is_exist == False:
            error_msg = f"GPT_SoVITS/pretrained_models/s2Gv{model_version}.pth 底模缺失，无法加载相应 LoRA 权重"
            print(error_msg)
            raise FileNotFoundError(error_msg)
        
        # 更新语言字典
        dict_language = dict_language_v1 if version == "v1" else dict_language_v2
        
        # 加载模型配置和权重
        dict_s2 = load_sovits_new(sovits_path)
        hps = dict_s2["config"]
        hps = DictToAttrRecursive(hps)
        hps.model.semantic_frame_rate = "25hz"
        
        # 检测版本
        if "enc_p.text_embedding.weight" not in dict_s2["weight"]:
            hps.model.version = "v2"  # v3model,v2symbols
        elif dict_s2["weight"]["enc_p.text_embedding.weight"].shape[0] == 322:
            hps.model.version = "v1"
        else:
            hps.model.version = "v2"
        version = hps.model.version
        
        # 创建模型
        if model_version not in v3v4set:
            vq_model = SynthesizerTrn(
                hps.data.filter_length // 2 + 1,
                hps.train.segment_size // hps.data.hop_length,
                n_speakers=hps.data.n_speakers,
                **hps.model,
            )
            model_version = version
        else:
            hps.model.version = model_version
            vq_model = SynthesizerTrnV3(
                hps.data.filter_length // 2 + 1,
                hps.train.segment_size // hps.data.hop_length,
                n_speakers=hps.data.n_speakers,
                **hps.model,
            )
        
        # 删除不需要的编码器（如果不是预训练模型）
        if "pretrained" not in sovits_path:
            try:
                del vq_model.enc_q
            except:
                pass
        
        # 移动到设备并设置精度
        if is_half:
            vq_model = vq_model.half().to(device)
        else:
            vq_model = vq_model.to(device)
        vq_model.eval()
        
        # 加载权重
        if if_lora_v3 == False:
            print("loading sovits_%s" % model_version, vq_model.load_state_dict(dict_s2["weight"], strict=False))
        else:
            # LoRA 模式
            path_sovits = path_sovits_v3 if model_version == "v3" else path_sovits_v4
            print(
                "loading sovits_%s pretrained_G" % model_version,
                vq_model.load_state_dict(load_sovits_new(path_sovits)["weight"], strict=False),
            )
            lora_rank = dict_s2["lora_rank"]
            lora_config = LoraConfig(
                target_modules=["to_k", "to_q", "to_v", "to_out.0"],
                r=lora_rank,
                lora_alpha=lora_rank,
                init_lora_weights=True,
            )
            vq_model.cfm = get_peft_model(vq_model.cfm, lora_config)
            print("loading sovits_%s_lora%s" % (model_version, lora_rank))
            vq_model.load_state_dict(dict_s2["weight"], strict=False)
            vq_model.cfm = vq_model.cfm.merge_and_unload()
            vq_model.eval()
        
        # 初始化相应的vocoder
        global hifigan_model, bigvgan_model
        if model_version == "v4":
            if hifigan_model is None:
                init_hifigan()

        
        print(f"SoVITS model changed to: {sovits_path}")
        
    except Exception as e:
        print(f"Error loading SoVITS model {sovits_path}: {e}")
        import traceback
        traceback.print_exc()
        raise

def change_gpt_weights(gpt_path):
    """Change GPT model weights - 使用与inference_webui.py相同的实现"""
    global hz, max_sec, t2s_model, config
    
    try:
        hz = 50
        dict_s1 = torch.load(gpt_path, map_location="cpu")
        config = dict_s1["config"]
        max_sec = config["data"]["max_sec"]
        
        # 创建新的模型实例
        t2s_model = Text2SemanticLightningModule(config, "****", is_train=False)
        t2s_model.load_state_dict(dict_s1["weight"])
        
        if is_half:
            t2s_model = t2s_model.half()
        t2s_model = t2s_model.to(device)
        t2s_model.eval()
        
        print(f"GPT model changed to: {gpt_path}")
        
    except Exception as e:
        print(f"Error loading GPT model {gpt_path}: {e}")
        import traceback
        traceback.print_exc()
        raise

# Text cutting functions
def cut1(inp):
    """Cut text into chunks of 4 sentences"""
    inp = inp.strip("\n")
    inps = inp.split("\n")
    split_idx = list(range(0, len(inps), 4))
    split_idx[-1] = None
    if len(split_idx) > 1:
        opts = []
        for idx in range(len(split_idx) - 1):
            opts.append("\n".join(inps[split_idx[idx]: split_idx[idx + 1]]))
        return "\n".join(opts)
    else:
        return inp

def cut2(inp):
    """Cut text into chunks of 50 characters"""
    inp = inp.strip("\n")
    inps = inp.split("\n")
    if len(inps) < 2:
        return inp
    opts = []
    summ = 0
    tmp_str = ""
    for i in range(len(inps)):
        summ += len(inps[i])
        tmp_str += inps[i]
        if summ > 50:
            summ = 0
            opts.append(tmp_str)
            tmp_str = ""
    if tmp_str != "":
        opts.append(tmp_str)
    if len(opts) > 1 and len(opts[-1]) < 4:
        opts[-2] = opts[-2] + opts[-1]
        opts = opts[:-1]
    return "\n".join(opts)

def cut3(inp):
    """Cut text by Chinese period"""
    inp = inp.strip("\n")
    return "\n".join(["%s。" % item for item in inp.strip("。").split("。")])

def cut4(inp):
    """Cut text by English period"""
    inp = inp.strip("\n")
    return "\n".join(["%s." % item for item in inp.strip(".").split(".")])

def cut5(inp):
    """Cut text by punctuation marks"""
    inp = inp.strip("\n")
    punds = {',', '.', ';', '?', '!', '、', '，', '。', '？', '！', '；', '：', '…'}
    mergeitems = []
    items = []
    
    for i, char in enumerate(inp):
        items.append(char)
        if char in punds:
            mergeitems.append("".join(items))
            items = []
    
    if items:
        if mergeitems:
            mergeitems[-1] += "".join(items)
        else:
            mergeitems.append("".join(items))
    
    opt = "\n".join(mergeitems)
    return opt

def process_text(texts):
    """Process text list by removing empty strings"""
    _texts = []
    for text in texts:
        if len(text.strip()) == 0:
            continue
        if text[-1] not in splits:
            text += "。" if dict_language.get(text, "zh") != "en" else "."
        _texts.append(text)
    return _texts

def merge_short_text_in_array(texts, threshold):
    """Merge short text segments"""
    if len(texts) < 2:
        return texts
    result = []
    text = ""
    for ele in texts:
        text += ele
        if len(text) >= threshold:
            result.append(text)
            text = ""
    if len(text) > 0:
        if len(result) == 0:
            result.append(text)
        else:
            result[len(result) - 1] += text
    return result

class WarningHandler:
    """Handle warning messages without Gradio"""
    def warning(self, message):
        print(f"WARNING: {message}")
        return message

# Create a warning handler instance
warning_handler = WarningHandler()

def resample(audio_tensor, sr0, sr1):
    """Resample audio tensor - 使用与inference_webui.py相同的实现"""
    global resample_transform_dict
    key = "%s-%s" % (sr0, sr1)
    if key not in resample_transform_dict:
        resample_transform_dict[key] = torchaudio.transforms.Resample(sr0, sr1).to(device)
    return resample_transform_dict[key](audio_tensor)

# Helper functions for audio processing
def norm_spec(x):
    """Normalize spectrogram - 使用与inference_webui.py相同的实现"""
    spec_min = -12
    spec_max = 2
    return (x - spec_min) / (spec_max - spec_min) * 2 - 1

def denorm_spec(x):
    """Denormalize spectrogram - 使用与inference_webui.py相同的实现"""
    spec_min = -12
    spec_max = 2
    return (x + 1) / 2 * (spec_max - spec_min) + spec_min

# Mel spectrogram functions
mel_fn = lambda x: mel_spectrogram_torch(
    x,
    **{
        "n_fft": 1024,
        "win_size": 1024,
        "hop_size": 256,
        "num_mels": 100,
        "sampling_rate": 24000,
        "fmin": 0,
        "fmax": None,
        "center": False,
    },
)

mel_fn_v4 = lambda x: mel_spectrogram_torch(
    x,
    **{
        "n_fft": 1280,
        "win_size": 1280,
        "hop_size": 320,
        "num_mels": 100,
        "sampling_rate": 32000,
        "fmin": 0,
        "fmax": None,
        "center": False,
    },
)

def init_hifigan():
    """Initialize HiFiGAN vocoder - 使用与inference_webui.py相同的实现"""
    global hifigan_model
    if hifigan_model is None:
        hifigan_model = Generator(
            initial_channel=100,
            resblock="1",
            resblock_kernel_sizes=[3, 7, 11],
            resblock_dilation_sizes=[[1, 3, 5], [1, 3, 5], [1, 3, 5]],
            upsample_rates=[10, 6, 2, 2, 2],
            upsample_initial_channel=512,
            upsample_kernel_sizes=[20, 12, 4, 4, 4],
            gin_channels=0,
            is_bias=True,
        )
        hifigan_model.remove_weight_norm()
        hifigan_model = hifigan_model.to(device).eval()
        if is_half:
            hifigan_model = hifigan_model.half()


# Initialize models on module import
try:
    init_models()
    load_models_from_paths(gpt_path, sovits_path)
    print("Models initialized successfully")
except Exception as e:
    print(f"Failed to initialize models: {e}")
    print("Models will need to be loaded manually")

def get_specc(hps, ref_wav_path):
    """Get spectrogram from reference audio"""
    audio, sr = librosa.load(ref_wav_path, sr=hps.data.sampling_rate)
    audio = torch.FloatTensor(audio)
    audio_norm = audio.unsqueeze(0)
    spec = spectrogram_torch(
        audio_norm,
        hps.data.filter_length,
        hps.data.sampling_rate,
        hps.data.hop_length,
        hps.data.win_length,
        center=False,
    )
    return spec

def load_models(gpt_path, sovits_path):
    """Load T2S and SoVITS models"""
    global t2s_model, vq_model, ssl_model, hps, hz, max_sec
    
    # Load T2S model
    dict_s1 = torch.load(gpt_path, map_location=device)
    config = dict_s1["config"]
    max_sec = config["data"]["max_sec"]
    t2s_model = Text2SemanticLightningModule(config, "****", is_train=False)
    t2s_model.load_state_dict(dict_s1["weight"])
    t2s_model = t2s_model.to(device).eval()
    if is_half:
        t2s_model = t2s_model.half()
    
    # Load SoVITS model
    dict_s2 = torch.load(sovits_path, map_location=device)
    hps = dict_s2["config"]
    
    vq_model = SynthesizerTrn(
        hps.data.filter_length // 2 + 1,
        hps.train.segment_size // hps.data.hop_length,
        **hps.model
    )
    vq_model.load_state_dict(dict_s2["weight"], strict=False)
    vq_model = vq_model.to(device).eval()
    if is_half:
        vq_model = vq_model.half()
    
    # Load SSL model
    ssl_model = cnhubert.get_model()
    ssl_model = ssl_model.to(device)
    if is_half:
        ssl_model = ssl_model.half()

def change_sovits_weights(sovits_path):
    """Change SoVITS model weights - 使用与inference_webui.py相同的实现"""
    global vq_model, hps, version, model_version, dict_language, if_lora_v3
    
    try:
        from peft import LoraConfig, get_peft_model
        from process_ckpt import load_sovits_new
        
        version_info, model_version, if_lora_v3 = get_sovits_version_from_path_fast(sovits_path)
        print(f"Loading SoVITS model: {sovits_path}, version: {version_info}, model_version: {model_version}, lora: {if_lora_v3}")
        
        # 检查v3/v4底模是否存在
        path_sovits_v3 = "GPT_SoVITS/pretrained_models/s2Gv3.pth"
        path_sovits_v4 = "GPT_SoVITS/pretrained_models/gsv-v4-pretrained/s2Gv4.pth"
        is_exist_s2gv3 = os.path.exists(path_sovits_v3)
        is_exist_s2gv4 = os.path.exists(path_sovits_v4)
        is_exist = is_exist_s2gv3 if model_version == "v3" else is_exist_s2gv4
        
        if if_lora_v3 == True and is_exist == False:
            error_msg = f"GPT_SoVITS/pretrained_models/s2Gv{model_version}.pth 底模缺失，无法加载相应 LoRA 权重"
            print(error_msg)
            raise FileNotFoundError(error_msg)
        
        # 更新语言字典
        dict_language = dict_language_v1 if version == "v1" else dict_language_v2
        
        # 加载模型配置和权重
        dict_s2 = load_sovits_new(sovits_path)
        hps = dict_s2["config"]
        hps = DictToAttrRecursive(hps)
        hps.model.semantic_frame_rate = "25hz"
        
        # 检测版本
        if "enc_p.text_embedding.weight" not in dict_s2["weight"]:
            hps.model.version = "v2"  # v3model,v2symbols
        elif dict_s2["weight"]["enc_p.text_embedding.weight"].shape[0] == 322:
            hps.model.version = "v1"
        else:
            hps.model.version = "v2"
        version = hps.model.version
        
        # 创建模型
        if model_version not in v3v4set:
            vq_model = SynthesizerTrn(
                hps.data.filter_length // 2 + 1,
                hps.train.segment_size // hps.data.hop_length,
                n_speakers=hps.data.n_speakers,
                **hps.model,
            )
            model_version = version
        else:
            hps.model.version = model_version
            vq_model = SynthesizerTrnV3(
                hps.data.filter_length // 2 + 1,
                hps.train.segment_size // hps.data.hop_length,
                n_speakers=hps.data.n_speakers,
                **hps.model,
            )
        
        # 删除不需要的编码器（如果不是预训练模型）
        if "pretrained" not in sovits_path:
            try:
                del vq_model.enc_q
            except:
                pass
        
        # 移动到设备并设置精度
        if is_half:
            vq_model = vq_model.half().to(device)
        else:
            vq_model = vq_model.to(device)
        vq_model.eval()
        
        # 加载权重
        if if_lora_v3 == False:
            print("loading sovits_%s" % model_version, vq_model.load_state_dict(dict_s2["weight"], strict=False))
        else:
            # LoRA 模式
            path_sovits = path_sovits_v3 if model_version == "v3" else path_sovits_v4
            print(
                "loading sovits_%s pretrained_G" % model_version,
                vq_model.load_state_dict(load_sovits_new(path_sovits)["weight"], strict=False),
            )
            lora_rank = dict_s2["lora_rank"]
            lora_config = LoraConfig(
                target_modules=["to_k", "to_q", "to_v", "to_out.0"],
                r=lora_rank,
                lora_alpha=lora_rank,
                init_lora_weights=True,
            )
            vq_model.cfm = get_peft_model(vq_model.cfm, lora_config)
            print("loading sovits_%s_lora%s" % (model_version, lora_rank))
            vq_model.load_state_dict(dict_s2["weight"], strict=False)
            vq_model.cfm = vq_model.cfm.merge_and_unload()
            vq_model.eval()
        
        # 初始化相应的vocoder
        global hifigan_model, bigvgan_model
        if model_version == "v4":
            if hifigan_model is None:
                init_hifigan()

        print(f"SoVITS model changed to: {sovits_path}")
        
    except Exception as e:
        print(f"Error loading SoVITS model {sovits_path}: {e}")
        import traceback
        traceback.print_exc()
        raise

def change_gpt_weights(gpt_path):
    """Change GPT model weights - 使用与inference_webui.py相同的实现"""
    global hz, max_sec, t2s_model, config
    
    try:
        hz = 50
        dict_s1 = torch.load(gpt_path, map_location="cpu")
        config = dict_s1["config"]
        max_sec = config["data"]["max_sec"]
        
        # 创建新的模型实例
        t2s_model = Text2SemanticLightningModule(config, "****", is_train=False)
        t2s_model.load_state_dict(dict_s1["weight"])
        
        if is_half:
            t2s_model = t2s_model.half()
        t2s_model = t2s_model.to(device)
        t2s_model.eval()
        
        print(f"GPT model changed to: {gpt_path}")
        
    except Exception as e:
        print(f"Error loading GPT model {gpt_path}: {e}")
        import traceback
        traceback.print_exc()
        raise

# Text cutting functions
def cut1(inp):
    """Cut text into chunks of 4 sentences"""
    inp = inp.strip("\n")
    inps = inp.split("\n")
    split_idx = list(range(0, len(inps), 4))
    split_idx[-1] = None
    if len(split_idx) > 1:
        opts = []
        for idx in range(len(split_idx) - 1):
            opts.append("\n".join(inps[split_idx[idx]: split_idx[idx + 1]]))
        return "\n".join(opts)
    else:
        return inp

def cut2(inp):
    """Cut text into chunks of 50 characters"""
    inp = inp.strip("\n")
    inps = inp.split("\n")
    if len(inps) < 2:
        return inp
    opts = []
    summ = 0
    tmp_str = ""
    for i in range(len(inps)):
        summ += len(inps[i])
        tmp_str += inps[i]
        if summ > 50:
            summ = 0
            opts.append(tmp_str)
            tmp_str = ""
    if tmp_str != "":
        opts.append(tmp_str)
    if len(opts) > 1 and len(opts[-1]) < 4:
        opts[-2] = opts[-2] + opts[-1]
        opts = opts[:-1]
    return "\n".join(opts)

def cut3(inp):
    """Cut text by Chinese period"""
    inp = inp.strip("\n")
    return "\n".join(["%s。" % item for item in inp.strip("。").split("。")])

def cut4(inp):
    """Cut text by English period"""
    inp = inp.strip("\n")
    return "\n".join(["%s." % item for item in inp.strip(".").split(".")])

def cut5(inp):
    """Cut text by punctuation marks"""
    inp = inp.strip("\n")
    punds = {',', '.', ';', '?', '!', '、', '，', '。', '？', '！', '；', '：', '…'}
    mergeitems = []
    items = []
    
    for i, char in enumerate(inp):
        items.append(char)
        if char in punds:
            mergeitems.append("".join(items))
            items = []
    
    if items:
        if mergeitems:
            mergeitems[-1] += "".join(items)
        else:
            mergeitems.append("".join(items))
    
    opt = "\n".join(mergeitems)
    return opt

def process_text(texts):
    """Process text list by removing empty strings"""
    _texts = []
    for text in texts:
        if len(text.strip()) == 0:
            continue
        if text[-1] not in splits:
            text += "。" if dict_language.get(text, "zh") != "en" else "."
        _texts.append(text)
    return _texts

def merge_short_text_in_array(texts, threshold):
    """Merge short text segments"""
    if len(texts) < 2:
        return texts
    result = []
    text = ""
    for ele in texts:
        text += ele
        if len(text) >= threshold:
            result.append(text)
            text = ""
    if len(text) > 0:
        if len(result) == 0:
            result.append(text)
        else:
            result[len(result) - 1] += text
    return result

class WarningHandler:
    """Handle warning messages without Gradio"""
    def warning(self, message):
        print(f"WARNING: {message}")
        return message

# Create a warning handler instance
warning_handler = WarningHandler()

def get_tts_wav(
    ref_wav_path,
    prompt_text,
    prompt_language,
    text,
    text_language,
    how_to_cut="不切",
    top_k=20,
    top_p=0.6,
    temperature=0.6,
    ref_free=False,
    speed=1,
    if_freeze=False,
    inp_refs=None,
    sample_steps=8,
    if_sr=False,
    pause_second=0.3,
):
    """
    Core TTS inference function without Gradio dependencies
    """
    global cache
    
    # Input validation without Gradio warnings
    if not ref_wav_path:
        warning_handler.warning("请上传参考音频")
        return None, None
    if not text:
        warning_handler.warning("请填入推理文本")
        return None, None
    
    t = []
    if prompt_text is None or len(prompt_text) == 0:
        ref_free = True
    
    # v3/v4模型暂不支持ref_free模式
    if model_version in v3v4set:
        ref_free = False
    else:
        if_sr = False  # v1/v2不支持超分
    
    t0 = ttime()
    prompt_language = dict_language[prompt_language]
    text_language = dict_language[text_language]

    if not ref_free:
        prompt_text = prompt_text.strip("\n")
        if prompt_text[-1] not in splits:
            prompt_text += "。" if prompt_language != "en" else "."
        print("实际输入的参考文本:", prompt_text)
    
    text = text.strip("\n")
    print("实际输入的目标文本:", text)
    
    zero_wav = np.zeros(
        int(hps.data.sampling_rate * pause_second),
        dtype=np.float16 if is_half else np.float32,
    )
    zero_wav_torch = torch.from_numpy(zero_wav)
    if is_half:
        zero_wav_torch = zero_wav_torch.half().to(device)
    else:
        zero_wav_torch = zero_wav_torch.to(device)
    
    if not ref_free:
        with torch.no_grad():
            wav16k, sr = librosa.load(ref_wav_path, sr=16000)
            if wav16k.shape[0] > 160000 or wav16k.shape[0] < 48000:
                warning_handler.warning("参考音频在3~10秒范围外，请更换！")
                return None, None
            
            wav16k = torch.from_numpy(wav16k)
            if is_half:
                wav16k = wav16k.half().to(device)
            else:
                wav16k = wav16k.to(device)
            wav16k = torch.cat([wav16k, zero_wav_torch])
            
            ssl_content = ssl_model.model(wav16k.unsqueeze(0))["last_hidden_state"].transpose(1, 2)
            codes = vq_model.extract_latent(ssl_content)
            prompt_semantic = codes[0, 0]
            prompt = prompt_semantic.unsqueeze(0).to(device)

    t1 = ttime()
    t.append(t1 - t0)

    # Text cutting logic
    if how_to_cut == "凑四句一切":
        text = cut1(text)
    elif how_to_cut == "凑50字一切":
        text = cut2(text)
    elif how_to_cut == "按中文句号。切":
        text = cut3(text)
    elif how_to_cut == "按英文句号.切":
        text = cut4(text)
    elif how_to_cut == "按标点符号切":
        text = cut5(text)
    
    while "\n\n" in text:
        text = text.replace("\n\n", "\n")
    
    print("实际输入的目标文本(切句后):", text)
    texts = text.split("\n")
    texts = process_text(texts)
    texts = merge_short_text_in_array(texts, 5)
    audio_opt = []
    
    if not ref_free:
        phones1, bert1, norm_text1 = get_phones_and_bert(prompt_text, prompt_language, version)
    
    for i_text, text in enumerate(texts):
        # Skip empty text
        if len(text.strip()) == 0:
            continue
        if text[-1] not in splits:
            text += "。" if text_language != "en" else "."
        print("实际输入的目标文本(每句):", text)
        
        phones2, bert2, norm_text2 = get_phones_and_bert(text, text_language, version)
        print("前端处理后的文本(每句):", norm_text2)
        
        if not ref_free:
            bert = torch.cat([bert1, bert2], 1)
            all_phoneme_ids = torch.LongTensor(phones1 + phones2).to(device).unsqueeze(0)
        else:
            bert = bert2
            all_phoneme_ids = torch.LongTensor(phones2).to(device).unsqueeze(0)

        bert = bert.to(device).unsqueeze(0)
        all_phoneme_len = torch.tensor([all_phoneme_ids.shape[-1]]).to(device)

        t2 = ttime()
        
        if i_text in cache and if_freeze:
            pred_semantic = cache[i_text]
        else:
            with torch.no_grad():
                pred_semantic, idx = t2s_model.model.infer_panel(
                    all_phoneme_ids,
                    all_phoneme_len,
                    None if ref_free else prompt,
                    bert,
                    top_k=top_k,
                    top_p=top_p,
                    temperature=temperature,
                    early_stop_num=hz * max_sec,
                )
                pred_semantic = pred_semantic[:, -idx:].unsqueeze(0)
                cache[i_text] = pred_semantic
        
        t3 = ttime()
        
        # Audio generation - handling both v1/v2 and v3/v4 models
        if model_version not in v3v4set:
            # For v1/v2 models
            refers = []
            if inp_refs:
                for path in inp_refs:
                    try:
                        refer = get_spepc(hps, path.name).to(dtype).to(device)
                        refers.append(refer)
                    except:
                        print(f"Error loading reference {path}")
            if len(refers) == 0:
                refers = [get_spepc(hps, ref_wav_path).to(dtype).to(device)]
                
            audio = vq_model.decode(
                pred_semantic, torch.LongTensor(phones2).to(device).unsqueeze(0), refers, speed=speed
            )[0][0]
        else:
            # For v3/v4 models - 使用正确的函数调用
            refer = get_spepc(hps, ref_wav_path).to(device).to(dtype)
            phoneme_ids0 = torch.LongTensor(phones1).to(device).unsqueeze(0)
            phoneme_ids1 = torch.LongTensor(phones2).to(device).unsqueeze(0)
            
            fea_ref, ge = vq_model.decode_encp(prompt.unsqueeze(0), phoneme_ids0, refer)
            ref_audio, sr = torchaudio.load(ref_wav_path)
            ref_audio = ref_audio.to(device).float()
            if ref_audio.shape[0] == 2:
                ref_audio = ref_audio.mean(0).unsqueeze(0)
            
            tgt_sr = 24000 if model_version == "v3" else 32000
            if sr != tgt_sr:
                ref_audio = resample(ref_audio, sr, tgt_sr)
                
            mel2 = mel_fn(ref_audio) if model_version == "v3" else mel_fn_v4(ref_audio)
            mel2 = norm_spec(mel2)
            T_min = min(mel2.shape[2], fea_ref.shape[2])
            mel2 = mel2[:, :, :T_min]
            fea_ref = fea_ref[:, :, :T_min]
            
            Tref = 468 if model_version == "v3" else 500
            Tchunk = 934 if model_version == "v3" else 1000
            if T_min > Tref:
                mel2 = mel2[:, :, -Tref:]
                fea_ref = fea_ref[:, :, -Tref:]
                T_min = Tref
            chunk_len = Tchunk - T_min
            mel2 = mel2.to(dtype)
            
            fea_todo, ge = vq_model.decode_encp(pred_semantic, phoneme_ids1, refer, ge, speed)
            cfm_resss = []
            idx = 0
            
            while True:
                fea_todo_chunk = fea_todo[:, :, idx : idx + chunk_len]
                if fea_todo_chunk.shape[-1] == 0:
                    break
                idx += chunk_len
                fea = torch.cat([fea_ref, fea_todo_chunk], 2).transpose(2, 1)
                cfm_res = vq_model.cfm.inference(
                    fea, torch.LongTensor([fea.size(1)]).to(fea.device), mel2, sample_steps, inference_cfg_rate=0
                )
                cfm_res = cfm_res[:, :, mel2.shape[2] :]
                mel2 = cfm_res[:, :, -T_min:]
                fea_ref = fea_todo_chunk[:, :, -T_min:]
                cfm_resss.append(cfm_res)
                
            cfm_res = torch.cat(cfm_resss, 2)
            cfm_res = denorm_spec(cfm_res)
            
            # Initialize vocoder if needed
            if model_version == "v4":
                if hifigan_model is None:
                    init_hifigan()
                vocoder_model = hifigan_model
                
            with torch.inference_mode():
                wav_gen = vocoder_model(cfm_res)
                audio = wav_gen[0][0]
        
        # Audio post-processing
        max_audio = torch.abs(audio).max()
        if max_audio > 1:
            audio = audio / max_audio
        audio_opt.append(audio)
        audio_opt.append(zero_wav_torch)
        
        t4 = ttime()
        t.extend([t2 - t1, t3 - t2, t4 - t3])
        t1 = ttime()
    
    print("%.3f\t%.3f\t%.3f\t%.3f" % (t[0], sum(t[1::3]), sum(t[2::3]), sum(t[3::3])))
    audio_opt = torch.cat(audio_opt, 0)
    
    # Output sampling rate based on model version
    if model_version in {"v1", "v2"}:
        opt_sr = 32000
    elif model_version == "v3":
        opt_sr = 24000
    else:  # v4
        opt_sr = 48000
    
    audio_opt = audio_opt.cpu().detach().numpy()
    
    yield opt_sr, (audio_opt * 32767).astype(np.int16)

# Get spectrogram from reference audio - 使用与inference_webui.py相同的函数名get_spepc
def get_specc(hps, filename):
    audio, sampling_rate = librosa.load(filename, sr=int(hps.data.sampling_rate))
    audio = torch.FloatTensor(audio)
    maxx = audio.abs().max()
    if maxx > 1:
        audio /= min(2, maxx)
    audio_norm = audio
    audio_norm = audio_norm.unsqueeze(0)
    spec = spectrogram_torch(
        audio_norm,
        hps.data.filter_length,
        hps.data.sampling_rate,
        hps.data.hop_length,
        hps.data.win_length,
        center=False,
    )
    return spec

# 添加get_spepc别名以保持与inference_webui.py的兼容性
get_spepc = get_specc


def init_hifigan():
    """Initialize HiFiGAN vocoder - 使用与inference_webui.py相同的实现"""
    global hifigan_model, bigvgan_model
    hifigan_model = Generator(
        initial_channel=100,
        resblock="1",
        resblock_kernel_sizes=[3, 7, 11],
        resblock_dilation_sizes=[[1, 3, 5], [1, 3, 5], [1, 3, 5]],
        upsample_rates=[10, 6, 2, 2, 2],
        upsample_initial_channel=512,
        upsample_kernel_sizes=[20, 12, 4, 4, 4],
        gin_channels=0,
        is_bias=True,
    )
    hifigan_model.eval()
    hifigan_model.remove_weight_norm()
    
    # 使用环境变量中的vocoder路径
    if os.path.exists(vocoder_path):
        state_dict_g = torch.load(vocoder_path, map_location="cpu")
        print("loading vocoder", hifigan_model.load_state_dict(state_dict_g))
    
    if bigvgan_model:
        bigvgan_model = bigvgan_model.cpu()
        bigvgan_model = None
        try:
            torch.cuda.empty_cache()
        except:
            pass
    
    if is_half:
        hifigan_model = hifigan_model.half().to(device)
    else:
        hifigan_model = hifigan_model.to(device)
