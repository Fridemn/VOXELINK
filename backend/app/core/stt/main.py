"""
FastAPI版本的语音识别服务入口

这个模块是服务的入口点，导入并启动FastAPI应用。
"""

import os
import sys

# 将当前目录添加到模块搜索路径，确保可以导入app包
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 导入应用并启动
from app.main import start

if __name__ == "__main__":
    start()
