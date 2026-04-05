"""Collector code templates"""

from .api_template import API_TEMPLATE
from .scrape_template import SCRAPE_TEMPLATE

TEMPLATES = {
    "api": API_TEMPLATE,
    "scrape": SCRAPE_TEMPLATE,
}


def get_template(template_type: str) -> str:
    """获取指定类型的模板代码"""
    return TEMPLATES.get(template_type, API_TEMPLATE)


def render_template(template_type: str, class_name: str, name: str) -> str:
    """渲染模板，替换变量"""
    template = get_template(template_type)
    return template.replace("{{COLLECTOR_CLASS_NAME}}", class_name).replace("{{COLLECTOR_NAME}}", name)
