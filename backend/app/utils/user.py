"""
app/utils/user.py
用户工具函数。
- 提供加密和账号生成等基础工具。
- 供用户相关API和模型调用。
"""

import hashlib
import random
import time

from ..config.app_config import AppConfig
from ..models.user import User

# 延迟创建app_config实例
def get_app_config():
    if not hasattr(get_app_config, '_instance'):
        get_app_config._instance = AppConfig()
    return get_app_config._instance


# ------------------------------
#         密钥安全部分
# ------------------------------


def md5(s):
    s = s.encode("utf8")
    m = hashlib.md5()
    m.update(s)
    return m.hexdigest()


def generate_account():
    """基于时间戳和随机数生成唯一的7位账号"""
    timestamp = int(time.time() * 1000)  # 获取毫秒级时间戳
    random_suffix = random.randint(0, 99)  # 随机生成一个0到99的数字
    account = str(timestamp)[-5:] + f"{random_suffix:02d}"  # 时间戳后5位 + 2位随机数
    return account
