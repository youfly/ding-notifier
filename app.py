import os
import sys
import json
import hmac
import hashlib
import base64
import time
import logging
from flask import Flask, request, jsonify, Response
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 获取配置目录路径
CONFIG_DIR = os.environ.get('CONFIG_DIR', './config')
if not os.path.isabs(CONFIG_DIR):
    # 如果是相对路径，转为绝对路径（基于当前工作目录）
    CONFIG_DIR = os.path.join(os.getcwd(), CONFIG_DIR)

# 初始化 Jinja2 模板引擎
try:
    if not os.path.exists(CONFIG_DIR):
        logger.error(f"配置目录不存在: {CONFIG_DIR}")
        # 尝试创建目录以防万一
        os.makedirs(CONFIG_DIR, exist_ok=True)
        logger.info(f"已创建配置目录: {CONFIG_DIR}")
    
    env = Environment(loader=FileSystemLoader(CONFIG_DIR))
    logger.info(f"模板引擎初始化成功，目录: {CONFIG_DIR}")
    
    # 启动时打印目录内容
    files = os.listdir(CONFIG_DIR)
    logger.info(f"配置目录下文件列表: {files}")
except Exception as e:
    logger.error(f"模板引擎初始化失败: {e}")
    env = None

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

def generate_sign(secret, timestamp):
    """生成钉钉加签签名"""
    string_to_sign = f'{timestamp}\n{secret}'
    hmac_code = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return sign

def send_to_dingtalk(webhook_url, payload, secret=None):
    """发送消息到钉钉"""
    url = webhook_url
    
    # 如果提供了密钥，添加签名参数
    if secret:
        timestamp = str(round(time.time() * 1000))
        sign = generate_sign(secret, timestamp)
        separator = '&' if '?' in url else '?'
        url = f"{url}{separator}timestamp={timestamp}&sign={sign}"
        logger.info(f"已添加签名参数: timestamp={timestamp}, sign={sign[:10]}...")
    
    logger.info(f"正在发送到钉钉: {url}")
    logger.debug(f"请求 Payload: {json.dumps(payload, ensure_ascii=False)}")
    
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        logger.info(f"钉钉响应状态码: {response.status_code}")
        logger.info(f"钉钉响应内容: {response.text}")
        
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get('errcode') == 0:
                return True, "发送成功"
            else:
                return False, f"钉钉API错误: {res_data.get('errmsg')}"
        else:
            return False, f"HTTP错误: {response.status_code}"
    except Exception as e:
        logger.error(f"发送请求异常: {e}")
        return False, str(e)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "config_dir": CONFIG_DIR})

@app.route('/send', methods=['POST', 'GET'])
@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    logger.info("="*30)
    logger.info(f"收到请求: {request.method} {request.path}")
    logger.info(f"请求参数 (args): {request.args.to_dict()}")
    
    # 获取 Webhook URL 和 Secret
    webhook_url = request.args.get('url') or os.environ.get('DINGTALK_WEBHOOK_URL')
    secret = request.args.get('secret') or os.environ.get('DINGTALK_SECRET')
    
    if not webhook_url:
        logger.error("缺少 Webhook URL")
        return jsonify({"error": "缺少 webhook URL 参数或环境变量 DINGTALK_WEBHOOK_URL"}), 400
    
    # 获取模板名称
    template_name = request.args.get('template')
    logger.info(f"请求模板: {template_name}")
    
    # 解析请求数据
    data_vars = {}
    if request.is_json:
        logger.info("检测到 JSON 数据")
        json_data = request.get_json()
        # 扁平化 JSON 以便使用点分隔符访问
        data_vars = flatten_json(json_data)
        logger.info(f"扁平化后的变量: {data_vars}")
    elif request.form:
        logger.info("检测到表单数据")
        data_vars = dict(request.form)
        logger.info(f"表单变量: {data_vars}")
    elif request.data:
        # 尝试解析为 JSON，如果失败则作为纯文本
        try:
            json_data = json.loads(request.data)
            data_vars = flatten_json(json_data)
            logger.info(f"解析为 JSON 变量: {data_vars}")
        except json.JSONDecodeError:
            logger.info("数据既不是 JSON 也不是表单，作为纯文本处理")
            data_vars = {"raw_text": request.data.decode('utf-8')}
    else:
        logger.info("无请求体数据")

    # 构建钉钉消息
    dingtalk_payload = {}
    
    if template_name:
        if env is None:
            return jsonify({"error": "模板引擎未初始化"}), 500
        
        try:
            # 尝试加载模板 (自动添加 .json 后缀如果用户没写)
            template_file = template_name
            if not template_name.endswith('.json'):
                template_file = f"{template_name}.json"
            
            logger.info(f"正在加载模板文件: {template_file}")
            template = env.get_template(template_file)
            
            # 渲染模板
            rendered_content = template.render(**data_vars)
            logger.info(f"模板渲染成功: {rendered_content[:100]}...")
            
            # 解析渲染后的 JSON
            try:
                dingtalk_payload = json.loads(rendered_content)
                logger.info("渲染内容解析为 JSON 成功")
            except json.JSONDecodeError as e:
                logger.error(f"渲染内容不是有效的 JSON: {e}")
                return jsonify({"error": f"模板渲染结果不是有效的 JSON: {str(e)}"}), 400
                
        except TemplateNotFound:
            logger.error(f"模板文件未找到: {template_file}")
            # 列出可用模板帮助调试
            try:
                available_files = os.listdir(CONFIG_DIR)
                return jsonify({
                    "error": f"模板文件未找到: {template_file}",
                    "available_files": available_files,
                    "config_dir": CONFIG_DIR
                }), 404
            except Exception as list_err:
                return jsonify({"error": f"模板文件未找到: {template_file}", "list_error": str(list_err)}), 404
        except Exception as e:
            logger.error(f"模板处理异常: {e}")
            return jsonify({"error": f"模板处理错误: {str(e)}"}), 500
    else:
        # 无模板模式：直接使用 POST 的数据作为 payload
        logger.info("无模板模式，直接使用请求数据作为 Payload")
        if request.is_json:
            dingtalk_payload = request.get_json()
        elif request.form:
            # 表单数据转换为 text 消息
            content = "\n".join([f"{k}: {v}" for k, v in request.form.items()])
            dingtalk_payload = {
                "msgtype": "text",
                "text": {"content": content}
            }
        else:
            return jsonify({"error": "无模板模式下必须提供 JSON 或表单数据"}), 400

    # 发送到钉钉
    success, message = send_to_dingtalk(webhook_url, dingtalk_payload, secret)
    
    if success:
        return jsonify({"status": "success", "message": message}), 200
    else:
        return jsonify({"status": "failed", "error": message}), 502

if __name__ == '__main__':
    # 延迟导入以避免某些环境下的问题
    import urllib.parse
    
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    
    logger.info("="*30)
    logger.info("服务启动配置:")
    logger.info(f"  监听地址: {host}:{port}")
    logger.info(f"  配置目录 (绝对路径): {os.path.abspath(CONFIG_DIR)}")
    logger.info(f"  Webhook URL 配置: {'已设置' if os.environ.get('DINGTALK_WEBHOOK_URL') else '未设置'}")
    logger.info(f"  Secret 配置: {'已设置' if os.environ.get('DINGTALK_SECRET') else '未设置'}")
    
    if os.path.exists(CONFIG_DIR):
        files = os.listdir(CONFIG_DIR)
        logger.info(f"  配置目录内容: {files}")
    else:
        logger.warning(f"  配置目录不存在: {CONFIG_DIR}")
    
    logger.info("="*30)
    logger.info("服务已启动，等待请求...")
    
    app.run(host=host, port=port, debug=False)
