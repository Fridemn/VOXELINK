"""
app/utils/user.py
用户工具函数。
- 提供JWT生成、验证码、加密等工具。
- 供用户相关API和模型调用。
"""

import hashlib
import jwt
import random
import re
import secrets
import string
import time
from datetime import datetime, timedelta
from fastapi import HTTPException
from loguru import logger

from ..config.app_config import AppConfig
from ..models.user import User, VerificationCode
from .verification_code_platform import SendSms

# 延迟创建app_config实例
def get_app_config():
    if not hasattr(get_app_config, '_instance'):
        get_app_config._instance = AppConfig()
    return get_app_config._instance

# 获取jwt配置
def get_jwt_config():
    config = get_app_config()
    return config.jwt

# 验证码类型常量
USER_REGISTER_CODE = "register"
USER_LOGIN_CODE = "login"
USER_RESET_CODE = "reset"

# 获取JWT配置
jwt_config = get_jwt_config()
if jwt_config is None:
    raise ValueError("JWT configuration not found in app_config")

SECRET_KEY = jwt_config["secret_key"]
ALGORITHM = jwt_config.get("algorithm", "HS256")


# ------------------------------
#         邀请码部分
# ------------------------------


def generate_invitation_code(length=6):
    # 使用 secrets 生成一个包含字母和数字的随机字符串
    characters = string.ascii_letters + string.digits  # 可以根据需要增加字符集
    return "".join(secrets.choice(characters) for i in range(length))


# ------------------------------
#         密钥安全部分
# ------------------------------


# 生成 JWT Token
def create_jwt(current_user: User):
    # 设置有效期
    expiration = datetime.now() + timedelta(days=30)  # 七天过期
    payload = {
        "user_id": str(current_user.user_id),
    }
    headers = {"alg": ALGORITHM, "typ": "JWT"}
    # 生成 token
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM, headers=headers)
    return token


def decode_jwt(token: str):
    try:
        # 解码 JWT 并验证签名
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        return payload
    except jwt.ExpiredSignatureError:
        logger.error("Token 已过期!")
        raise HTTPException(status_code=401, detail="Token 已过期")
    except jwt.InvalidTokenError as e:
        logger.error(f"Token 无效! 错误信息: {e}")
        raise HTTPException(status_code=401, detail="Token 无效")
    except Exception as e:
        logger.error(f"解码 JWT 时发生错误: {str(e)}")
        raise HTTPException(status_code=400, detail="无效的 Token")


def md5(s):
    s = s.encode("utf8")
    m = hashlib.md5()
    m.update(s)
    return m.hexdigest()


# ------------------------------
#         获取用户部分
# ------------------------------


# 获取当前用户信息
def get_current_user(token: str):
    # result = redis_client.get(token)
    # if result == 'expired':
    #     raise HTTPException(status_code=401, detail="Token 已失效")
    # 1. 解码JWT并获取数据
    data = decode_jwt(token)
    logger.debug("data:" + str(data))

    if not data:
        # 如果 token 无效或已过期，返回 401 错误
        raise HTTPException(status_code=401, detail="Token 无效或已过期，请重新登录")

    # 2. 返回当前用户对象
    return data


async def get_code(phone: str, REDIS_PATH: str):
    # 验证手机号格式
    phone_regex = re.compile(r"^1[3-9]\d{9}$")
    if not phone_regex.match(phone):
        logger.error(f"手机号格式不正确！")
        raise HTTPException(status_code=400, detail="手机号格式不正确！")

    # 获取当前时间戳（单位：毫秒）
    timestamp = int(time.time() * 1000)
    # 使用时间戳的一部分与随机数结合
    seed = timestamp + random.randint(0, 9999)
    # 生成随机验证码
    code = (seed % 900000) + 100000
    # 注册
    # SMS_476785298
    # 登录
    # SMS_476855314
    # 重置密码
    # SMS_476695363
    if REDIS_PATH == USER_REGISTER_CODE:
        await SendSms.exec(phone, "SMS_476785298", str(code))
    elif REDIS_PATH == USER_LOGIN_CODE:
        await SendSms.exec(phone, "SMS_476855314", str(code))
    elif REDIS_PATH == USER_RESET_CODE:
        await SendSms.exec(phone, "SMS_476695363", str(code))

    # 存储验证码到数据库中
    from datetime import timedelta
    expires_at = datetime.now() + timedelta(seconds=300)  # 过期时间五分钟
    
    # 确定验证码类型
    if REDIS_PATH == USER_REGISTER_CODE:
        code_type = "register"
    elif REDIS_PATH == USER_LOGIN_CODE:
        code_type = "login"
    elif REDIS_PATH == USER_RESET_CODE:
        code_type = "reset"
    else:
        code_type = "unknown"
    
    # 保存到数据库
    await VerificationCode.create(
        phone=phone,
        code=str(code),
        type=code_type,
        expires_at=expires_at
    )
    
    # todo 发送验证码到手机
    logger.info(f"验证码发送到手机号 {phone}: {code}")
    return str(code)


# 验证码校验
async def check_code(code: str, phone: str, REDIS_PATH: str):
    # 确定验证码类型
    if REDIS_PATH == USER_REGISTER_CODE:
        code_type = "register"
    elif REDIS_PATH == USER_LOGIN_CODE:
        code_type = "login"
    elif REDIS_PATH == USER_RESET_CODE:
        code_type = "reset"
    else:
        code_type = "unknown"
    
    # 从数据库获取验证码
    verification_code = await VerificationCode.filter(
        phone=phone,
        type=code_type
    ).order_by("-created_at").first()
    
    if not verification_code:
        raise HTTPException(status_code=400, detail="验证码不存在！")
    
    # 检查验证码是否匹配
    if code != verification_code.code:
        raise HTTPException(status_code=400, detail="验证码错误！")
    
    # 检查是否过期
    if datetime.now() > verification_code.expires_at:
        raise HTTPException(status_code=400, detail="验证码已过期！")
    
    # 删除已使用的验证码
    await verification_code.delete()
    
    return True


def generate_account():
    """基于时间戳和随机数生成唯一的7位账号"""
    timestamp = int(time.time() * 1000)  # 获取毫秒级时间戳
    random_suffix = random.randint(0, 99)  # 随机生成一个0到99的数字
    account = str(timestamp)[-5:] + f"{random_suffix:02d}"  # 时间戳后5位 + 2位随机数
    return account
