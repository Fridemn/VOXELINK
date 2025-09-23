# VOXELINK

VOXELINK 是一个集成了语音识别(STT)、语音合成(TTS)和大语言模型的后端服务。

## 特性

- 🔊 **语音识别 (STT)**: 支持实时语音转文字
- 🗣️ **语音合成 (TTS)**: 支持文字转语音
- 🤖 **大语言模型**: 集成多种AI模型
- 🚀 **统一架构**: 单进程多服务，支持按需启用模块

## 快速开始

### 环境要求

- Python 3.8+
- pip
- git

### 安装依赖

```bash
# 安装后端依赖
cd backend
pip install -r requirements.txt

# 安装STT模块依赖 (可选)
cd app/core/stt
pip install -r requirements.txt

# 安装TTS模块依赖 (可选)
cd app/core/tts
pip install -r requirements.txt
```

### 启动服务

#### 方式1: 使用统一启动脚本 (推荐)

```bash
# 只启动后端服务
python start.py

# 启动后端 + STT服务
python start.py --enable-stt

# 启动后端 + TTS服务
python start.py --enable-tts

# 启动所有服务
python start.py --enable-stt --enable-tts

# 启动图形界面 (GUI)
python start.py --gui
```

#### 方式2: 使用图形界面 (GUI)

如果您更喜欢图形化界面，可以使用内置的GUI启动器：

```bash
python start.py --gui
```

GUI界面提供：
- ✅ 直观的配置选项
- ✅ 实时服务器输出显示
- ✅ 一键启动/停止服务
- ✅ 语音聊天功能，支持实时语音对话
- ✅ 录音、播放和发送音频
- ✅ 显示语音识别结果和AI回复
- ✅ 流式输出和TTS音频播放
```

#### 方式2: 直接启动后端

```bash
cd backend

# 只启动后端
python main.py

# 启动后端 + STT
python main.py --enable-stt

# 启动后端 + TTS
python main.py --enable-tts
```

### 服务端口

- **主服务**: http://localhost:8080
- **API文档**: http://localhost:8080/docs
- **替代文档**: http://localhost:8080/redoc

## API 接口

### 后端服务

- `GET /` - 服务状态检查
- `GET /system/*` - 系统相关接口
- `POST /llm/*` - 大语言模型接口

### STT 服务 (语音识别)

启用 `--enable-stt` 参数后可用：

- `POST /stt/asr/recognize` - 语音识别
- `GET /stt/asr/models` - 获取可用模型
- `POST /stt/vpr/register` - 声纹注册
- `POST /stt/vpr/verify` - 声纹验证

### TTS 服务 (语音合成)

启用 `--enable-tts` 参数后可用：

- `POST /tts/tts` - 语音合成
- `GET /tts/models/status` - 模型状态
- `POST /tts/models/switch` - 切换模型
- `GET /tts/characters` - 获取角色列表

## 配置

### 环境变量

```bash
# 数据库配置
DATABASE_URL=sqlite://db.sqlite3

# 服务配置
HOST=0.0.0.0
PORT=8080

# STT配置
STT_MODEL_PATH=/path/to/stt/model

# TTS配置
TTS_MODEL_PATH=/path/to/tts/model
```

### 配置文件

- `backend/app/config/` - 应用配置
- `backend/app/core/stt/config.json` - STT配置
- `backend/app/core/tts/config.json` - TTS配置

## 开发

### 项目结构

```
VOXELINK/
├── backend/                 # 后端服务
│   ├── main.py             # 主应用入口
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心模块
│   │   │   ├── stt/        # 语音识别模块
│   │   │   └── tts/       # 语音合成模块
│   │   ├── models/         # 数据模型
│   │   └── config/         # 配置
│   └── static/             # 静态文件
├── frontend/               # 前端服务
├── start.py                # 统一启动脚本
└── README.md
```

### 添加新模块

1. 在 `backend/app/core/` 下创建新模块
2. 在 `main.py` 中添加条件路由注册
3. 更新启动脚本参数
4. 更新文档

## 部署

### Docker 部署

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN pip install -r backend/requirements.txt
EXPOSE 8080

CMD ["python", "start.py", "--enable-stt", "--enable-tts"]
```

### 系统服务

```bash
# 创建服务文件
sudo tee /etc/systemd/system/voxellink.service > /dev/null <<EOF
[Unit]
Description=VOXELINK Backend Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/voxellink
ExecStart=/path/to/python start.py --enable-stt --enable-tts
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl enable voxellink
sudo systemctl start voxellink
```

## 故障排除

### 常见问题

1. **模块导入失败**
   - 检查依赖是否正确安装
   - 确认模块路径配置正确

2. **端口占用**
   - 使用 `--port` 参数指定其他端口
   - 检查端口是否被其他服务占用

3. **模型加载失败**
   - 检查模型文件是否存在
   - 确认模型路径配置正确

### 日志

日志文件位于 `backend/logs/` 目录下，按日期命名。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License