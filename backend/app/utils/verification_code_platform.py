"""
Verification Code Platform
短信验证码平台
"""

class SendSms:
    @staticmethod
    async def exec(phone: str, template: str, code: str):
        """
        发送短信验证码
        """
        # 这里应该实现实际的短信发送逻辑
        # 暂时返回成功
        print(f"Sending SMS to {phone} with template {template} and code {code}")
        return True