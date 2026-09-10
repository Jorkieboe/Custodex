import os
from fastapi import APIRouter
from backend.config import AppConfig, load_config, save_config

router = APIRouter(prefix="/api/config", tags=["config"])

@router.get("", response_model=AppConfig)
async def get_config() -> AppConfig:
    return load_config()

@router.put("", response_model=AppConfig)
async def update_config(payload: AppConfig) -> AppConfig:
    if payload.openai_api_key:
        os.environ["OPENAI_API_KEY"] = payload.openai_api_key
    save_config(payload)
    return payload