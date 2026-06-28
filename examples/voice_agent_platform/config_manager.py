import json
import os
from pydantic import BaseModel
from loguru import logger

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "agent_config.json")

class AgentConfig(BaseModel):
    system_prompt: str
    voice: str
    enabled_tools: list[str]

# The default safe fallback config
# This ensures that if the JSON is ever corrupted or missing, the pipeline never crashes.
DEFAULT_SYSTEM_PROMPT = """You are Priya, an AI sales agent for Prestige Realty.
You speak clearly and warmly. Keep responses concise."""

DEFAULT_CONFIG = AgentConfig(
    system_prompt=DEFAULT_SYSTEM_PROMPT,
    voice="priya",
    enabled_tools=["search_properties", "book_site_visit", "update_call_outcome"]
)

def get_config() -> AgentConfig:
    if not os.path.exists(CONFIG_FILE):
        logger.warning("agent_config.json not found. Using default config.")
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return AgentConfig(**data)
    except Exception as e:
        logger.error(f"Failed to load agent_config.json: {e}. Using default config.")
        return DEFAULT_CONFIG

def save_config(config: AgentConfig) -> bool:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(config.model_dump_json(indent=4))
        return True
    except Exception as e:
        logger.error(f"Failed to save agent_config.json: {e}")
        return False
