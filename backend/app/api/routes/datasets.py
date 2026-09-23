import io
import json
import logging
from typing import Any

from app.orchestration.pipeline import PipelineOrchestrator
from app.persistence.database import get_db
from app.persistence.repository import SessionRepository
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline")

class StrategyApprovalRequest(BaseModel):
    actions: list[dict[str, Any]]

def get_repo(db: Session = Depends(get_db)) -> SessionRepository:
    return SessionRepository(db)

@router.post("/upload", summary="Upload a CSV dataset")
async def upload_dataset(file: UploadFile = File(...), repo: SessionRepository = Depends(get_repo)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    try:
        contents = await file.read()
        session_id = PipelineOrchestrator.initialize_session(repo, contents)
        return {"session_id": session_id, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/analyze", summary="Run analysis agents")
async def analyze_dataset(session_id: str, repo: SessionRepository = Depends(get_repo)):
    try:
        return PipelineOrchestrator.analyze(repo, session_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{session_id}/strategy", summary="Generate cleaning strategy")
async def generate_strategy(session_id: str, custom_provider_url: str = None, repo: SessionRepository = Depends(get_repo)):
    try:
        return PipelineOrchestrator.generate_strategy(repo, session_id, custom_provider_url)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Run analysis first.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM Generation failed: {e!s}")

@router.post("/{session_id}/validate-strategy", summary="Validate and apply strategy")
async def validate_strategy(session_id: str, request: StrategyApprovalRequest, repo: SessionRepository = Depends(get_repo)):
    try:
        return PipelineOrchestrator.validate_strategy(repo, session_id, request.actions)
    except ValueError as e:
        try:
            violations = json.loads(str(e))
            raise HTTPException(status_code=400, detail={"message": "Strategy validation failed", "violations": violations})
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/execute", summary="Execute cleaning strategy")
async def execute_strategy(session_id: str, repo: SessionRepository = Depends(get_repo)):
    try:
        return PipelineOrchestrator.execute_strategy(repo, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Validate strategy first.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/validate-quality", summary="Post-cleaning validation")
async def validate_quality(session_id: str, repo: SessionRepository = Depends(get_repo)):
    try:
        return PipelineOrchestrator.validate_quality(repo, session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Missing original or cleaned dataset.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{session_id}/download", summary="Download cleaned dataset")
async def download_cleaned(session_id: str, repo: SessionRepository = Depends(get_repo)):
    try:
        csv_bytes = repo.get_cleaned_csv(session_id)
        return StreamingResponse(
            io.BytesIO(csv_bytes), 
            media_type="text/csv", 
            headers={"Content-Disposition": "attachment; filename=cleaned_dataset.csv"}
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Cleaned dataset not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
