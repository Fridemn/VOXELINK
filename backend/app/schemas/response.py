"""
app/schemas/response.py
通用响应数据模型。
- 定义API统一响应结构。
- 供各API接口返回数据时调用。
"""

from typing import Optional

from pydantic import BaseModel


class ResponseModel(BaseModel):
    message: str
    data: Optional[dict] = None  # data 字段可以包含任意字典数据，如果没有数据可以为空

    # 用于简化返回
    @classmethod
    def success(cls, message: str, data: Optional[dict] = None):
        return cls(message=message, data=data)

    @classmethod
    def fail(cls, message: str, data: Optional[dict] = None):

        return cls(message=message, data=data)
