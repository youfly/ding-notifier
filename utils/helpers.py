import hmac
import hashlib
import base64
import urllib.parse

def flatten_json(data, parent_key='', sep='.'):
    """扁平化 JSON 对象，支持点分隔符访问"""
    items = []
    for k, v in data.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_json(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def generate_dingtalk_sign(secret, timestamp):
    """生成钉钉加签签名"""
    string_to_sign = f'{timestamp}\n{secret}'
    hmac_code = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    return urllib.parse.quote_plus(base64.b64encode(hmac_code))
