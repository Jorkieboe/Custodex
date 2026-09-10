import os
import json
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
ENV_PATH = PROJECT_ROOT / ".env"

def _load_env_file() -> None:
    if ENV_PATH.exists():
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass

_load_env_file()

class AppConfig(BaseModel):
    default_llm_model: str = Field(default="gtp-4.1-mini")
    default_embedding_model: str = Field(default="text-embedding-multilingual-e5-base")
    lm_studio_endpoint: str = Field(default="http://localhost:1234/v1")
    llm_endpoint: str = Field(default="")
    embedding_endpoint: str = Field(default="")
    openai_api_key: str = Field(default="")
    recent_projects: List[str] = Field(default_factory=list)

def get_llm_endpoint(config: AppConfig) -> str:
    if config.llm_endpoint and config.llm_endpoint.strip():
        return config.llm_endpoint.strip()
    return config.lm_studio_endpoint.strip() if config.lm_studio_endpoint else "http://localhost:1234/v1"

def get_embedding_endpoint(config: AppConfig) -> str:
    if config.embedding_endpoint and config.embedding_endpoint.strip():
        return config.embedding_endpoint.strip()
    return config.lm_studio_endpoint.strip() if config.lm_studio_endpoint else "http://localhost:1234/v1"

def get_openai_api_key(config: Optional[AppConfig] = None) -> str:
    if config and config.openai_api_key and config.openai_api_key.strip():
        return config.openai_api_key.strip()
    return os.environ.get("OPENAI_API_KEY", "").strip()

def load_config() -> AppConfig:
    _load_env_file()
    if not CONFIG_PATH.exists():
        default_config = AppConfig()
        if not default_config.openai_api_key:
            default_config.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        save_config(default_config)
        return default_config

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfg = AppConfig(**data)
    if not cfg.openai_api_key and os.environ.get("OPENAI_API_KEY"):
        cfg.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    return cfg

def save_config(config: AppConfig) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)