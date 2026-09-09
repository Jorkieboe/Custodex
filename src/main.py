import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import load_config
from src.routers.config import router as config_router
from src.routers.documents import router as documents_router
from src.routers.nodes import router as nodes_router
from src.routers.projects import router as projects_router

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

class StatusResponse(BaseModel):
    status: str
    lm_studio_connected: bool
    lm_studio_endpoint: str
    default_llm_model: str
    default_embedding_model: str

@app.get("/api/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    config = load_config()
    lm_connected = False

    try:
        models_url = f"{config.lm_studio_endpoint.rstrip('/')}/models"
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(models_url)
            if resp.status_code == 200:
                lm_connected = True
    except Exception:
        lm_connected = False

    return StatusResponse(
        status="online",
        lm_studio_connected=lm_connected,
        lm_studio_endpoint=config.lm_studio_endpoint,
        default_llm_model=config.default_llm_model,
        default_embedding_model=config.default_embedding_model,
    )

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)