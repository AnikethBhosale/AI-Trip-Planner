"""Application configuration. Copy .env.example to .env and add your keys."""
from functools import lru_cache
import os

from dotenv import load_dotenv

load_dotenv()


@lru_cache
def settings() -> dict[str, str | int]:
    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "openai_base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        "openweather_api_key": os.getenv("OPENWEATHER_API_KEY", ""),
        "tavily_api_key": os.getenv("TAVILY_API_KEY", ""),
        "exchange_rate_api_key": os.getenv("EXCHANGERATE_API_KEY", ""),
        "osm_user_agent": os.getenv("OSM_USER_AGENT", "AtlasAITripPlanner/1.0 (local-development)"),
        "timeout": int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
        "max_replans": int(os.getenv("MAX_REPLAN_ATTEMPTS", "2")),
    }
