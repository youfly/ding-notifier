import os
import json
import logging
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)

class TemplateService:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.env = None
        self._init_engine()

    def _init_engine(self):
        if not os.path.exists(self.config_dir):
            logger.warning(f"配置目录不存在，正在创建: {self.config_dir}")
            os.makedirs(self.config_dir, exist_ok=True)
        
        self.env = Environment(loader=FileSystemLoader(self.config_dir))
        logger.info(f"模板引擎初始化成功，目录: {self.config_dir}")

    def render(self, template_name, data_vars):
        if not self.env:
            raise RuntimeError("模板引擎未初始化")

        # 自动补全后缀
        if not template_name.endswith('.json'):
            template_name += '.json'

        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound:
            available = os.listdir(self.config_dir)
            raise FileNotFoundError(f"模板 {template_name} 未找到。可用: {available}")

        # 注入时间变量
        now = datetime.now()
        time_vars = {
            'now': now.strftime('%Y-%m-%d %H:%M:%S'),
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'timestamp': int(now.timestamp()),
            'iso_time': now.isoformat(),
            'utc_time': now.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        context = {**time_vars, **data_vars}
        rendered = template.render(**context)
        return json.loads(rendered)
