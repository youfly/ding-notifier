import json
import logging
from flask import Blueprint, request, jsonify, current_app
from services.dingtalk import DingTalkService

logger = logging.getLogger(__name__)
webhook_bp = Blueprint('webhook', __name__)

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
            
def parse_request_body():
    """统一解析请求体，返回 (data_vars, raw_text)"""
    
    # 1. 如果声明了是 JSON
    if request.is_json:
        # 【关键修改】加入 silent=True，解析失败时返回 None 而不是抛出 400 异常
        json_data = request.get_json(silent=True)
        if json_data is not None:
            return json_data, None
            
    # 2. 如果是表单数据
    if request.form:
        return dict(request.form), None
        
    # 3. 如果有原始数据 (包括声明了 JSON 但解析失败的，以及纯文本)
    if request.data:
        try:
            # 尝试手动解析为 JSON
            return json.loads(request.data), None
        except (json.JSONDecodeError, UnicodeDecodeError):
            # 解析失败，降级为纯文本处理
            text = request.data.decode('utf-8', errors='ignore')
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
        flat_data = flatten_json(data_vars)
        content = "\n".join([f"{k}: {v}" for k, v in flat_data.items()]) or json.dumps(data_vars, ensure_ascii=False)
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
    
    # 1. 确定要发送给哪些机器人
    bot_names = request.args.get('bot', '').split(',')
    bot_names = [b.strip() for b in bot_names if b.strip()]
    
    bot_manager = current_app.config.get('BOT_MANAGER')
    targets = [] # 存放 (名称, url, secret) 的元组列表
    
    if bot_names and bot_manager and bot_manager.bots:
        # 模式 A：指定了具体的 bot 名称 (如 ?bot=ops_team,dev_team)
        for name in bot_names:
            bot_conf = bot_manager.get_bot(name)
            if bot_conf:
                targets.append((name, bot_conf.get('url'), bot_conf.get('secret')))
            else:
                logger.warning(f"请求的机器人 '{name}' 未在 bots.json 中配置")
    elif bot_manager and bot_manager.get_bot('default'):
        # 模式 B：没指定名称，但配置了 default
        bot_conf = bot_manager.get_bot('default')
        targets.append(('default', bot_conf.get('url'), bot_conf.get('secret')))
    else:
        # 模式 C：降级兼容旧版 (读取 URL 参数或环境变量)
        url = request.args.get('url') or current_app.config.get('DINGTALK_WEBHOOK_URL')
        secret = request.args.get('secret') or current_app.config.get('DINGTALK_SECRET')
        if url:
            targets.append(('env/param', url, secret))
            
    if not targets or not any(t[1] for t in targets):
        return jsonify({"error": "未找到可用的机器人配置 (缺少 bot 参数、bots.json 或环境变量)"}), 400

    # 2. 解析数据 & 构建 Payload (逻辑与之前完全一致)
    data_vars, raw_text = parse_request_body()
    template_name = request.args.get('template')
    
    try:
        if template_name:
            template_svc = current_app.config['TEMPLATE_SERVICE']
            payload = template_svc.render(template_name, data_vars)
        else:
            payload = build_smart_payload(data_vars, raw_text)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"构建Payload失败: {e}")
        return jsonify({"error": str(e)}), 400

    # 3. 循环发送给所有目标机器人
    results = {}
    all_success = True
    
    for name, url, secret in targets:
        if not url:
            results[name] = "缺少 URL 配置"
            all_success = False
            continue
            
        success, msg = DingTalkService.send_message(url, payload, secret)
        results[name] = msg
        if not success:
            all_success = False
        logger.info(f"机器人 [{name}] 发送结果: {msg}")
            
    status_code = 200 if all_success else 502
    return jsonify({
        "status": "success" if all_success else "partial_success/failed", 
        "results": results
    }), status_code
