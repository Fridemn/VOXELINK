"""
app/models/user.py
用户数据模型。
- 定义用户ORM模型及其字段。
- 供数据库与业务逻辑统一调用。
"""

import uuid
from tortoise.models import Model
from tortoise import fields


class User(Model):
    user_id = fields.UUIDField(pk=True, default=uuid.uuid4, index=True)
    phone = fields.CharField(default="", max_length=100, description="电话号")
    account = fields.CharField(default="", max_length=100, description="账户")  # 往往和phone相同
    username = fields.CharField(default="", max_length=100, description="用户名")
    password = fields.CharField(default="", max_length=100, description="密码")
    points = fields.IntField(default=0, description="积分")
    invitation_code = fields.CharField(default="", max_length=100, description="邀请码")
    qq_id = fields.CharField(null=True, default=None, max_length=100, description="QQ ID")


class VerificationCode(Model):
    id = fields.IntField(pk=True)
    phone = fields.CharField(max_length=20, description="手机号")
    code = fields.CharField(max_length=10, description="验证码")
    type = fields.CharField(max_length=20, description="验证码类型")  # register, login, reset
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    expires_at = fields.DatetimeField(description="过期时间")

    class Meta:
        table = "verification_codes"
        app = "models"
