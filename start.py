#!/usr/bin/env python3
"""
VOXELINK 统一启动脚本

启动 VOXELINK 后端服务，支持通过命令行参数控制是否启用 STT 和 TTS 模块。

使用方法:
  python start.py                    # 只启动后端
  python start.py --enable-stt       # 启动后端 + STT
  python start.py --enable-tts       # 启动后端 + TTS
  python start.py --enable-stt --enable-tts  # 启动所有服务
  python start.py --gui              # 启动 GUI 界面

参数:
  --enable-stt    启用语音识别 (STT) 服务
  --enable-tts    启用语音合成 (TTS) 服务
  --host HOST     绑定主机 (默认: 0.0.0.0)
  --port PORT     绑定端口 (默认: 8080)
  --reload        启用自动重载 (开发模式)
  --gui           启动图形用户界面 (GUI)
  --help          显示帮助信息
"""

import sys
import os
from pathlib import Path

# 修复Windows下的Unicode编码问题
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 添加backend目录到Python路径
backend_dir = Path(__file__).parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 添加backend/app目录到Python路径
app_dir = backend_dir / "app"
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

# 导入主应用
from main import create_app

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="VOXELINK Backend Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python start.py                          # 只启动后端服务
  python start.py --enable-stt             # 启动后端 + STT服务
  python start.py --enable-tts             # 启动后端 + TTS服务
  python start.py --enable-stt --enable-tts # 启动所有服务
  python start.py --port 9000              # 指定端口启动
  python start.py --reload                 # 开发模式启动
  python start.py --gui                    # 启动 GUI 界面

服务说明:
  后端服务 (Backend): 核心API服务，端口 8080
  STT服务 (Speech-to-Text): 语音识别服务，路由前缀 /stt
  TTS服务 (Text-to-Speech): 语音合成服务，路由前缀 /tts

API文档:
  http://localhost:{port}/docs
        """
    )

    parser.add_argument(
        "--enable-stt",
        action="store_true",
        help="启用语音识别 (STT) 服务"
    )
    parser.add_argument(
        "--enable-tts",
        action="store_true",
        help="启用语音合成 (TTS) 服务"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="绑定主机 (默认: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="绑定端口 (默认: 8080)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用自动重载 (开发模式)"
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="启动图形用户界面 (GUI)"
    )

    args = parser.parse_args()

    # 如果指定了 --gui，启动 GUI 界面
    if args.gui:
        try:
            from gui import main as gui_main
            gui_main()
            sys.exit(0)
        except ImportError as e:
            print(f"❌ 无法启动 GUI: {e}")
            print("请确保已安装 PyQt6: pip install PyQt6")
            sys.exit(1)

    print("🚀 启动 VOXELINK 后端服务...")
    print(f"📍 主机: {args.host}")
    print(f"🔌 端口: {args.port}")
    print(f"🔄 重载: {'启用' if args.reload else '禁用'}")

    # 显示启用的服务
    services = ["后端"]
    if args.enable_stt:
        services.append("STT")
    if args.enable_tts:
        services.append("TTS")

    print(f"📦 启用的服务: {', '.join(services)}")
    print("-" * 50)

    # 创建应用
    app = create_app(enable_stt=args.enable_stt, enable_tts=args.enable_tts)

    # 启动服务
    import uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )