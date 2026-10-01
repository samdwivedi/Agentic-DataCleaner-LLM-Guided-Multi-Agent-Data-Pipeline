import io
import json
import logging
import re
import asyncio
from typing import Any

from app.orchestration.pipeline import PipelineOrchestrator
from app.celery_app import celery_app
from app.tasks import analyze_task, generate_strategy_task, validate_strategy_task, execute_strategy_task, validate_quality_task
from app.persistence.database import get_db
from app.persistence.repository import SessionRepository
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline")

# ── Validation helpers ────────────────────────────────────────────────────────
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

def _validate_session_id(session_id: str) -> str:
    """Validate session_id is a proper UUID to prevent path traversal / injection."""
    if not _UUID_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format.")
    return session_id


def _safe_error_detail(e: Exception, *, fallback: str = "Internal processing error.") -> str:
    """Return a safe, non-leaking error message for API consumers."""
    # Only expose ValueError messages (they are our own domain errors).
    # Everything else gets a generic message to avoid stack trace / DB schema leaks.
    if isinstance(e, (ValueError, FileNotFoundError)):
        return str(e)
    logger.exception("Unexpected error: %s", e)
    return fallback


class StrategyApprovalRequest(BaseModel):
    actions: list[dict[str, Any]]

def get_repo(db: Session = Depends(get_db)) -> SessionRepository:
    return SessionRepository(db)


# ── Max upload size constant ──────────────────────────────────────────────────
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/upload", summary="Upload a CSV dataset")
async def upload_dataset(file: UploadFile = File(...), repo: SessionRepository = Depends(get_repo)):
    # 1. Extension check
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    
    # 2. Content-type check (browsers set this on upload)
    if file.content_type and file.content_type not in ("text/csv", "application/vnd.ms-excel", "application/octet-stream"):
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {file.content_type}. Expected text/csv.")
    
    # 3. Size check (header-based, if available)
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB.")
    
    try:
        contents = await file.read()
        
        # 4. Size check (actual bytes read)
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB.")
        
        # 5. Content sniffing — reject binary files disguised as .csv
        try:
            head = contents[:4096].decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File does not appear to be a valid UTF-8 CSV.")
        
        session_id = await asyncio.to_thread(PipelineOrchestrator.initialize_session, repo, contents)
        return {"session_id": session_id, "filename": file.filename}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=_safe_error_detail(e))

@router.post("/{session_id}/analyze", summary="Run analysis agents (Async)")
async def analyze_dataset(session_id: str, repo: SessionRepository = Depends(get_repo)):
    _validate_session_id(session_id)
    task = analyze_task.delay(session_id)
    return {"task_id": task.id}

@router.post("/{session_id}/strategy", summary="Generate cleaning strategy (Async)")
async def generate_strategy(session_id: str, repo: SessionRepository = Depends(get_repo)):
    _validate_session_id(session_id)
    task = generate_strategy_task.delay(session_id)
    return {"task_id": task.id}

@router.post("/{session_id}/validate-strategy", summary="Validate strategy (Async)")
async def validate_strategy(session_id: str, request: StrategyApprovalRequest, repo: SessionRepository = Depends(get_repo)):
    _validate_session_id(session_id)
    task = validate_strategy_task.delay(session_id, request.actions)
    return {"task_id": task.id}

@router.post("/{session_id}/execute", summary="Execute cleaning strategy (Async)")
async def execute_strategy(session_id: str, repo: SessionRepository = Depends(get_repo)):
    _validate_session_id(session_id)
    task = execute_strategy_task.delay(session_id)
    return {"task_id": task.id}

@router.post("/{session_id}/validate-quality", summary="Post-cleaning validation (Async)")
async def validate_quality(session_id: str, repo: SessionRepository = Depends(get_repo)):
    _validate_session_id(session_id)
    task = validate_quality_task.delay(session_id)
    return {"task_id": task.id}

@router.get("/task/{task_id}", summary="Check Task Status")
async def get_task_status(task_id: str):
    task_result = celery_app.AsyncResult(task_id)
    
    if task_result.state == 'PENDING':
        return {"status": "PENDING"}
    elif task_result.state == 'SUCCESS':
        return {"status": "SUCCESS", "result": task_result.result}
    elif task_result.state == 'FAILURE':
        return {"status": "FAILURE", "error": str(task_result.info)}
    else:
        return {"status": task_result.state}

import pandas as pd

@router.get("/{session_id}/download", summary="Download cleaned dataset")
async def download_cleaned(session_id: str, format: str = "csv", repo: SessionRepository = Depends(get_repo)):
    _validate_session_id(session_id)
    format = format.lower()
    valid_formats = {"csv", "parquet", "xlsx", "json"}
    if format not in valid_formats:
        raise HTTPException(status_code=400, detail=f"Invalid format. Supported formats: {', '.join(valid_formats)}")

    try:
        csv_bytes = repo.get_cleaned_csv(session_id)
        
        if format == "csv":
            return StreamingResponse(
                io.BytesIO(csv_bytes), 
                media_type="text/csv", 
                headers={"Content-Disposition": f"attachment; filename=cleaned_dataset.csv"}
            )
            
        # Parse into DataFrame for conversion
        df = pd.read_csv(io.BytesIO(csv_bytes))
        output = io.BytesIO()
        
        if format == "parquet":
            df.to_parquet(output, index=False)
            output.seek(0)
            return StreamingResponse(
                output, 
                media_type="application/vnd.apache.parquet", 
                headers={"Content-Disposition": f"attachment; filename=cleaned_dataset.parquet"}
            )
        elif format == "xlsx":
            df.to_excel(output, index=False, engine="openpyxl")
            output.seek(0)
            return StreamingResponse(
                output, 
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                headers={"Content-Disposition": f"attachment; filename=cleaned_dataset.xlsx"}
            )
        elif format == "json":
            df.to_json(output, orient="records")
            output.seek(0)
            return StreamingResponse(
                output, 
                media_type="application/json", 
                headers={"Content-Disposition": f"attachment; filename=cleaned_dataset.json"}
            )
            
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Cleaned dataset not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))
