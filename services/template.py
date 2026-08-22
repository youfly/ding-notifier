import os
import json
import logging
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)


def json_escape(value):
    """转义为 JSON 字符串内容（不含外层引号），防止引号/反斜杠破坏 JSON"""
    return json.dumps(str(value), ensure_ascii=False)[1:-1]


def format_time(value, fmt='%Y-%m-%d %H:%M:%S', tz=None):
    """时间格式化：dateutil 万能解析，失败则原样返回"""
    if value is None or value == '':
        return ''
    try:
        # Unix 时间戳单独处理（dateutil 对纯数字不敏感）
        if isinstance(value, (int, float)) or str(value).strip().isdigit():
            ts = float(value)
            if ts > 1e12:          # 毫秒转秒
                ts /= 1000
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            dt = date_parser.parse(str(value))   # 一行，万能解析

        if tz is not None:
            dt = dt.astimezone(timezone(timedelta(hours=float(tz))))
        elif dt.tzinfo is not None:
            dt = dt.astimezone()

        return dt.strftime(fmt)
    except Exception:
        return str(value)          # 解析不了就原样返回，绝不丢信息


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
        # 注册自定义 filter
        self.env.filters['json_escape'] = json_escape
        self.env.filters['format_time'] = format_time
        logger.info(f"模板引擎初始化成功，目录: {self.config_dir}")

    def render(self, template_name, data_vars):
        if not self.env:
            raise RuntimeError("模板引擎未初始化")

        if not template_name.endswith('.json'):
            template_name += '.json'

        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound:
            available = os.listdir(self.config_dir)
            raise FileNotFoundError(f"模板 {template_name} 未找到。可用: {available}")

        now = datetime.now()
        time_vars = {
            '_now': now.strftime('%Y-%m-%d %H:%M:%S'),  # 最常用的：当前本地时间 (如 2026-08-22 16:30:00)
            '_date': now.strftime('%Y-%m-%d'),          # 当前日期 (如 2026-08-22)
            '_time': now.strftime('%H:%M:%S'),          # 当前时间 (如 16:30:00)
            '_timestamp': int(now.timestamp())          # 当前 Unix 时间戳 (秒)
        }

        context = {**time_vars, **data_vars}
        rendered = template.render(**context)
        return json.loads(rendered)
