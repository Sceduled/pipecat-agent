import re
from loguru import logger

def render_template(template_str: str, context: dict) -> str:
    """
    Replaces Jinja2/Mustache style tags e.g. {{lead_name}} or {{ company_name }} with values from context.
    If a key is missing from context, replaces it with an appropriate default or fallback.
    """
    if not template_str:
        return ""
        
    def replace_match(match):
        key = match.group(1).strip()
        val = context.get(key)
        if val is not None and str(val).strip() != "":
            return str(val)
            
        # Smart fallbacks for standard agent variables
        defaults = {
            "lead_name": "there",
            "company_name": context.get("company_name") or "our organization",
            "agent_name": context.get("name") or "AI Assistant",
            "niche": context.get("niche") or "customer service",
            "knowledge_base": context.get("knowledge_base") or ""
        }
        return str(defaults.get(key, ""))
        
    pattern = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
    rendered = pattern.sub(replace_match, template_str)
    return rendered.strip()
