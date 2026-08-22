import logging
import time
import hmac
import hashlib
import base64
import requests
import urllib.parse

logger = logging.getLogger(__name__)

def generate_dingtalk_sign(secret, timestamp):
    """生成钉钉加签签名"""
    string_to_sign = f'{timestamp}\n{secret}'
    hmac_code = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    return urllib.parse.quote_plus(base64.b64encode(hmac_code))
    
class DingTalkService:
    @staticmethod
    def send_message(webhook_url, payload, secret=None):
        url = webhook_url
        
        # 1. 处理加签
        if secret:
            timestamp = str(round(time.time() * 1000))
            sign = generate_dingtalk_sign(secret, timestamp)
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}timestamp={timestamp}&sign={sign}"
            logger.debug(f"已添加签名: timestamp={timestamp}")
        
        # 2. 发送请求
        logger.info(f"正在发送到钉钉: {url}")
        headers = {'Content-Type': 'application/json'}
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            res_data = response.json()
            
            if response.status_code == 200 and res_data.get('errcode') == 0:
                return True, "发送成功"
            
            error_msg = res_data.get('errmsg', f"HTTP {response.status_code}")
            logger.error(f"钉钉API错误: {error_msg}")
            return False, error_msg
            
        except Exception as e:
            logger.error(f"发送请求异常: {e}")
            return False, str(e)
