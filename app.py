import os
from flask import Flask
from config import Config
from services.template import TemplateService
from routes.webhook import webhook_bp
from services.bot_manager import BotManager

def create_app():
    Config.setup_logging()
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(Config)
    
    # 初始化模板服务并挂载到 app
    app.config['TEMPLATE_SERVICE'] = TemplateService(Config.TEMPLATE_DIR)    
    
    # 初始化多钉钉机器人管理器
    app.config['BOT_MANAGER'] = BotManager(Config.CONFIG_DIR)

    # 注册路由蓝图
    app.register_blueprint(webhook_bp)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)
