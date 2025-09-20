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
    account = fields.CharField(default="", max_length=100, description="账户")


