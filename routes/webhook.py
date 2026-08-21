import json
import logging
from flask import Blueprint, request, jsonify, current_app
from services.dingtalk import DingTalkService

logger = logging.getLogger(__name__)
webhook_bp = Blueprint('webhook', __name__)

def parse_request_body():
    """统一解析请求体，返回 (data_vars, raw_text)"""
    if request.is_json:
        return request.get_json(), None
    if request.form:
        return dict(request.form), None
    if request.data:
        try:
            return json.loads(request.data), None
        except json.JSONDecodeError:
            text = request.data.decode('utf-8')
            return {"raw_text": text}, text
    return {}, None

def build_smart_payload(data_vars, raw_text):
    """无模板时的智能 Payload 构建"""
    # 如果已经是标准钉钉格式，直接透传
    if isinstance(data_vars, dict) and 'msgtype' in data_vars:
        return data_vars
        
    # 否则转为纯文本
    if raw_text:
        content = raw_text
    elif isinstance(data_vars, dict):
        content = "\n".join([f"{k}: {v}" for k, v in data_vars.items()]) or json.dumps(data_vars, ensure_ascii=False)
    else:
        content = str(data_vars)
        
    return {"msgtype": "text", "text": {"content": content}}

@webhook_bp.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "config_dir": current_app.config['CONFIG_DIR']})

@webhook_bp.route('/send', methods=['POST', 'GET'])
@webhook_bp.route('/webhook', methods=['POST', 'GET'])
def handle_webhook():
    logger.info(f"收到请求: {request.method} {request.path}")
    
    # 1. 获取鉴权参数
    webhook_url = request.args.get('url') or current_app.config.get('DINGTALK_WEBHOOK_URL')
    secret = request.args.get('secret') or current_app.config.get('DINGTALK_SECRET')
    if not webhook_url:
        return jsonify({"error": "缺少 webhook URL"}), 400

    # 2. 解析数据
    data_vars, raw_text = parse_request_body()
    template_name = request.args.get('template')
    
    # 3. 构建 Payload
    try:
        if template_name:
            template_svc = current_app.config['TEMPLATE_SERVICE']
            # 如果是嵌套JSON，先扁平化
            if isinstance(data_vars, dict) and not raw_text:
                from utils.helpers import flatten_json
                data_vars = flatten_json(data_vars)
            payload = template_svc.render(template_name, data_vars)
        else:
            payload = build_smart_payload(data_vars, raw_text)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"构建Payload失败: {e}")
        return jsonify({"error": str(e)}), 400

    # 4. 发送并返回
    success, msg = DingTalkService.send_message(webhook_url, payload, secret)
    status_code = 200 if success else 502
    return jsonify({"status": "success" if success else "failed", "message": msg}), status_code
