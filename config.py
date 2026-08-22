import os
import logging

class Config:
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5005))
    # 基础配置目录 (存放 bots.json 等)
    CONFIG_DIR = os.environ.get('CONFIG_DIR', './config')
    
    # 确保路径是绝对路径
    if not os.path.isabs(CONFIG_DIR):
        CONFIG_DIR = os.path.join(os.getcwd(), CONFIG_DIR)
        
    # 模板专用目录
    TEMPLATE_DIR = os.path.join(CONFIG_DIR, 'templates')

    @classmethod
    def setup_logging(cls):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
