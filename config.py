import os
import logging

class Config:
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    CONFIG_DIR = os.environ.get('CONFIG_DIR', './config')
    
    # 确保路径是绝对路径
    if not os.path.isabs(CONFIG_DIR):
        CONFIG_DIR = os.path.join(os.getcwd(), CONFIG_DIR)

    @classmethod
    def setup_logging(cls):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
