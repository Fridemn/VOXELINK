# VOXELINK-Module-Voice

VOXELINK语音服务模块，提供语音识别和声纹识别功能。

## 项目结构

项目采用FastAPI框架，重构为标准的Web API服务：

```
app/                    # 应用主目录
├── api/                # API路由
│   ├── __init__.py     # 路由初始化
│   ├── asr.py          # 语音识别API
│   ├── vpr.py          # 声纹识别API
│   └── ws.py           # WebSocket API
├── core/               # 核心配置
│   ├── __init__.py
│   ├── config.py       # 配置管理
│   └── security.py     # 安全相关
├── models/             # 数据模型
│   ├── __init__.py
│   └── schemas.py      # Pydantic模型
├── services/           # 业务逻辑服务
│   ├── __init__.py
│   ├── asr_service.py  # 语音识别服务
│   └── vpr_service.py  # 声纹识别服务
├── __init__.py
└── main.py             # 应用入口
```

## 功能特性

- **语音识别**: 基于FunASR模型的中文语音识别
- **声纹识别**: 基于ModelScope的声纹识别、比对和管理
- **多接口支持**: 同时支持REST API和WebSocket接口
- **缓存机制**: 提供声纹识别结果缓存，提高性能

## 安装与启动

### 环境要求

- Python 3.8+
- 依赖库（见requirements.txt）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

Windows:
```
start_service.bat
```

Linux/Mac:
```
bash start_service.sh
```

或者直接运行:
```
python main.py
```

## API接口

启动后可访问Swagger文档：http://localhost:8765/docs

### 主要接口

#### 语音识别

- `POST /asr/recognize`: 识别音频并返回文本

#### 声纹识别

- `POST /vpr/register`: 注册声纹
- `POST /vpr/identify`: 识别声纹
- `POST /vpr/compare`: 比对两段音频的声纹
- `POST /vpr/remove`: 删除声纹
- `GET /vpr/list`: 获取声纹列表

#### WebSocket

- `/ws`: WebSocket接口，支持实时语音识别和声纹识别

## 配置说明

配置文件为`config.json`，主要配置项：

- `host`: 服务监听地址
- `port`: 服务监听端口
- `require_auth`: 是否启用认证
- `api_key`: API密钥
- `asr_model_dir`: 语音识别模型目录
- `vpr_model`: 声纹识别模型
- `vpr_similarity_threshold`: 声纹匹配阈值
