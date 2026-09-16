import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import load_config, get_llm_endpoint, get_embedding_endpoint
from backend.routers.config import router as config_router
from backend.routers.documents import router as documents_router
from backend.routers.nodes import router as nodes_router
from backend.routers.projects import router as projects_router
from backend.routers.schema import router as schema_router
from backend.routers.metadata import router as metadata_router
from backend.routers.embeddings import router as embeddings_router
from backend.routers.export import router as export_router

app = FastAPI(
    title="Custodex API",
    description="Local-first visual workbench and RAG dataset preparation editor",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config_router)
app.include_router(projects_router)
app.include_router(documents_router)
app.include_router(nodes_router)
app.include_router(schema_router)
app.include_router(metadata_router)
app.include_router(embeddings_router)
app.include_router(export_router)

class StatusResponse(BaseModel):
    status: str
    lm_studio_connected: bool
    lm_studio_endpoint: str
    llm_endpoint: str = ""
    embedding_endpoint: str = ""
    has_openai_api_key: bool = False
    default_llm_model: str
    default_embedding_model: str
    llm_connected: bool = False
    embedding_connected: bool = False

@app.get("/api/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    config = load_config()
    llm_connected = False
    embedding_connected = False

    llm_url = get_llm_endpoint(config)
    embedding_url = get_embedding_endpoint(config)

    headers = {}
    if config.openai_api_key:
        headers["Authorization"] = f"Bearer {config.openai_api_key}"

    async with httpx.AsyncClient(timeout=1.5) as client:
        try:
            resp = await client.get(f"{llm_url.rstrip('/')}/models", headers=headers)
            if resp.status_code == 200:
                llm_connected = True
        except Exception:
            llm_connected = False

        try:
            if embedding_url.rstrip('/') == llm_url.rstrip('/'):
                embedding_connected = llm_connected
            else:
                resp_emb = await client.get(f"{embedding_url.rstrip('/')}/models", headers=headers)
                if resp_emb.status_code == 200:
                    embedding_connected = True
        except Exception:
            embedding_connected = False

    return StatusResponse(
        status="online",
        lm_studio_connected=llm_connected or embedding_connected,
        lm_studio_endpoint=config.lm_studio_endpoint,
        llm_endpoint=llm_url,
        embedding_endpoint=embedding_url,
        has_openai_api_key=bool(config.openai_api_key),
        default_llm_model=config.default_llm_model,
        default_embedding_model=config.default_embedding_model,
        llm_connected=llm_connected,
        embedding_connected=embedding_connected,
    )

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)