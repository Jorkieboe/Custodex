import os
import pytest
from unittest.mock import patch
from backend.config import (
    AppConfig,
    get_embedding_endpoint,
    get_llm_endpoint,
    get_openai_api_key,
    load_config,
)
from backend.routers.metadata import _normalize_model_name, _get_llm_client_for_model

def test_separated_model_endpoints_and_api_key():
    cfg = AppConfig(
        default_llm_model="gtp-4.1-mini",
        default_embedding_model="text-embedding-multilingual-e5-base",
        lm_studio_endpoint="http://localhost:1234/v1",
        llm_endpoint="https://api.openai.com/v1",
        embedding_endpoint="http://localhost:1234/v1",
        openai_api_key="sk-test-mock-key",
    )

    assert get_llm_endpoint(cfg) == "https://api.openai.com/v1"
    assert get_embedding_endpoint(cfg) == "http://localhost:1234/v1"
    assert get_openai_api_key(cfg) == "sk-test-mock-key"

def test_env_api_key_fallback():
    cfg = AppConfig(openai_api_key="")
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key-12345"}):
        assert get_openai_api_key(cfg) == "sk-env-key-12345"

def test_model_name_normalization():
    assert _normalize_model_name("gtp-4.1-mini") == "gpt-4.1-mini"
    assert _normalize_model_name("gpt-4o") == "gpt-4o"
    assert _normalize_model_name(" local-model ") == "local-model"

def test_llm_client_creation_with_openai_model():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-mock-key"}):
        client, model, endpoint = _get_llm_client_for_model("gtp-4.1-mini")
        assert model == "gpt-4.1-mini"
        assert client.api_key == "sk-mock-key"