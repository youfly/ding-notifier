#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉消息 Webhook 转发器
功能：
1. 支持通过 URL 参数 template 指定模板文件（位于 config 目录）
2. 支持 JSON POST body，变量从 JSON 路径引用
3. 支持表单参数，直接使用参数名作为变量
4. 使用 Jinja2 渲染模板
"""

import os
import json
import hmac
import hashlib
import time
import urllib.parse
import requests
from flask import Flask, request, jsonify, abort
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

app = Flask(__name__)

# 配置 - CONFIG_DIR 可通过环境变量覆盖，默认使用容器内 /app/config
CONFIG_DIR = os.environ.get('CONFIG_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config'))
DINGTALK_WEBHOOK_URL = os.environ.get('DINGTALK_WEBHOOK_URL', '')
DINGTALK_SECRET = os.environ.get('DINGTALK_SECRET', '')

# 确保 config 目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)

# 初始化 Jinja2 环境
jinja_env = Environment(
    loader=FileSystemLoader(CONFIG_DIR),
    autoescape=False
)


def generate_sign(secret: str, timestamp: str) -> str:
    """
    生成钉钉加签签名
    secret: 加签密钥 (SEC开头)
    timestamp: 时间戳 (毫秒)
    """
    string_to_sign = f'{timestamp}\n{secret}'
    sign = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    return urllib.parse.quote_plus(sign, safe='')


def extract_json_value(data: dict, path: str):
    """
    根据点分隔的路径从嵌套的 JSON 中提取值
    例如：path="a.b.c" 会提取 data['a']['b']['c']
    """
    keys = path.split('.')
    value = data
    try:
        for key in keys:
            if isinstance(value, dict):
                value = value[key]
            else:
                return None
        return value
    except (KeyError, TypeError):
        return None


def build_variables(request_data: dict, is_json: bool) -> dict:
    """
    构建模板变量字典
    - 如果是 JSON：支持点分隔路径引用（如 alert.title）
    - 如果是表单：直接使用参数名
    """
    variables = {}
    
    if is_json:
        # 递归展平 JSON 对象，支持点分隔键名
        def flatten(d, parent_key=''):
            items = []
            if isinstance(d, dict):
                for k, v in d.items():
                    new_key = f"{parent_key}.{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten(v, new_key).items())
                    else:
                        items.append((new_key, v))
            else:
                items.append((parent_key, d))
            return dict(items)
        
        variables = flatten(request_data)
        # 同时保留原始数据以便直接访问
        variables['raw'] = request_data
    else:
        # 表单数据直接使用
        variables = request_data
    
    return variables


def render_template(template_name: str, variables: dict) -> dict:
    """
    渲染模板并返回钉钉消息格式
    """
    try:
        template = jinja_env.get_template(template_name)
        rendered = template.render(**variables)
        
        # 尝试解析为 JSON（钉钉消息通常是 JSON 格式）
        try:
            message_data = json.loads(rendered)
        except json.JSONDecodeError:
            # 如果不是 JSON，则作为 text 消息处理
            message_data = {
                "msgtype": "text",
                "text": {
                    "content": rendered
                }
            }
        
        return message_data
    except TemplateNotFound:
        raise ValueError(f"模板文件未找到: {template_name}")
    except Exception as e:
        raise ValueError(f"模板渲染失败: {str(e)}")


def send_to_dingtalk(message_data: dict, webhook_url: str = None, secret: str = None) -> dict:
    """
    发送消息到钉钉
    支持加签安全设置
    """
    url = webhook_url or DINGTALK_WEBHOOK_URL
    ding_secret = secret or DINGTALK_SECRET
    
    if not url:
        raise ValueError("未配置钉钉 Webhook URL")
    
    # 如果配置了密钥，则添加签名参数
    if ding_secret:
        timestamp = str(round(time.time() * 1000))
        sign = generate_sign(ding_secret, timestamp)
        # 拼接签名参数
        separator = '&' if '?' in url else '?'
        url = f"{url}{separator}timestamp={timestamp}&sign={sign}"
    
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, json=message_data, headers=headers, timeout=10)
    
    result = response.json() if response.text else {}
    
    return {
        "status_code": response.status_code,
        "response": result,
        "success": response.status_code == 200 and result.get('errcode', 0) == 0
    }


@app.route('/webhook', methods=['POST'])
def webhook():
    """
    主 Webhook 入口
    支持查询参数:
    - template: 模板文件名（可选，位于 config 目录）
    - webhook_url: 覆盖默认的钉钉 Webhook URL（可选）
    - secret: 覆盖默认的钉钉加签密钥（可选）
    """
    template_name = request.args.get('template')
    override_webhook = request.args.get('webhook_url')
    override_secret = request.args.get('secret')
    
    # 判断请求类型
    if request.is_json:
        request_data = request.get_json(force=True)
        is_json = True
    else:
        # 表单数据或普通参数
        request_data = request.form.to_dict()
        if not request_data:
            # 尝试从 query params 获取
            request_data = request.args.to_dict()
        is_json = False
    
    # 构建变量
    variables = build_variables(request_data, is_json)
    
    # 如果有 template 参数，使用模板渲染
    if template_name:
        try:
            message_data = render_template(template_name, variables)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    else:
        # 无模板时，尝试直接使用 JSON 或创建默认文本消息
        if is_json:
            message_data = request_data
        else:
            # 将表单参数转换为文本消息
            content = "\n".join([f"{k}: {v}" for k, v in variables.items()])
            message_data = {
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
    
    # 发送到钉钉
    try:
        result = send_to_dingtalk(message_data, override_webhook, override_secret)
        if result['success']:
            return jsonify({
                "status": "success",
                "message": "消息已发送到钉钉",
                "dingtalk_response": result['response']
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "钉钉返回错误",
                "dingtalk_response": result['response']
            }), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"请求钉钉失败: {str(e)}"}), 503


@app.route('/health', methods=['GET'])
def health():
    """健康检查端点"""
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
