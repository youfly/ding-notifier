import os
import json
import logging

logger = logging.getLogger(__name__)

class BotManager:
    def __init__(self, config_dir):
        self.bots_file = os.path.join(config_dir, 'bots.json')
        self.bots = {}
        self._load_bots()

    def _load_bots(self):
        if not os.path.exists(self.bots_file):
            logger.warning(f"未找到多机器人配置文件 {self.bots_file}，将降级使用环境变量/URL参数模式。")
            return
        
        try:
            with open(self.bots_file, 'r', encoding='utf-8') as f:
                self.bots = json.load(f)
            logger.info(f"✅ 成功加载 {len(self.bots)} 个钉钉机器人: {list(self.bots.keys())}")
        except Exception as e:
            logger.error(f"❌ 加载 bots.json 失败: {e}")

    def get_bot(self, name):
        return self.bots.get(name)
