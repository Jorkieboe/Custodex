import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.services.export_service import ValidationGateBlockedError, build_rag_bundle
from backend.services.project_manager import get_project_connection
from backend.services.validation_service import validate_project

router = APIRouter(prefix="/api/projects/{project_id}", tags=["export"])

@router.get("/validate")
async def get_project_validation(project_id: str):
    conn = get_project_connection(project_id)
    return validate_project(conn, project_id)

@router.get("/export")
async def export_rag_bundle(project_id: str):
    conn = get_project_connection(project_id)
    try:
        zip_bytes, filename = build_rag_bundle(conn, project_id)
    except ValidationGateBlockedError as err:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Export blocked: project contains validation issues.",
                "validation": err.validation_result,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Bundle-Filename": filename,
        },
    )