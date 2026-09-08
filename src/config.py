import json
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

class AppConfig(BaseModel):
    default_llm_model: str = Field(default="local-model")
    default_embedding_model: str = Field(default="text-embedding-nomic-embed-text-v1.5")
    lm_studio_endpoint: str = Field(default="http://localhost:1234/v1")
    recent_projects: List[str] = Field(default_factory=list)

def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        default_config = AppConfig()
        save_config(default_config)
        return default_config

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return AppConfig(**data)

def save_config(config: AppConfig) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)