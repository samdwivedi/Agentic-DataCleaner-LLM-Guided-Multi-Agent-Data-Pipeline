"""
Data Cleaning Pipeline API
──────────────────────────
Stateful (file-based) API endpoints for the multi-agent data cleaning pipeline.
Data is stored locally under ``data/sessions/<uuid>/``.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent.profiler import ProfilerAgent
from agent.validator import SchemaValidator, ValidationSchema, ColumnRule
from agent.anomaly import AnomalyDetector
from agent.strategist import StrategistAgent
from agent.strategist.providers import OllamaProvider
from agent.strategy_validator import StrategyValidator, ValidatedCleaningStrategy
from agent.executor import ExecutorAgent
from agent.quality import QualityAssessor, QualityConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline")

SESSION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/sessions"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_session_path(session_id: str) -> str:
    """Get the root directory for a given session."""
    path = os.path.join(SESSION_DIR, session_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return path


def save_json(path: str, data: BaseModel | dict) -> None:
    """Save Pydantic model or dict to JSON."""
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, BaseModel):
            f.write(data.model_dump_json(indent=2))
        else:
            json.dump(data, f, indent=2)


def load_json(path: str) -> dict:
    """Load dict from JSON."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Resource not found: {os.path.basename(path)}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def infer_schema(df: pd.DataFrame) -> ValidationSchema:
    """Create a permissive base schema from a DataFrame."""
    columns = {}
    for col in df.columns:
        dtype = str(df[col].dtype)
        columns[col] = ColumnRule(
            expected_dtype=dtype,
            nullable=True,
        )
    return ValidationSchema(required_columns=list(df.columns), columns=columns)


# ── Models ────────────────────────────────────────────────────────────────────

class StrategyApprovalRequest(BaseModel):
    actions: List[Dict[str, Any]]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload", summary="Upload a CSV dataset")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload a dataset, create a session, and save the original file."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    session_id = str(uuid.uuid4())
    path = os.path.join(SESSION_DIR, session_id)
    os.makedirs(path, exist_ok=True)

    file_path = os.path.join(path, "original.csv")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Ensure it parses
    try:
        pd.read_csv(file_path)
    except Exception as e:
        shutil.rmtree(path)
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {str(e)}")

    logger.info("Session %s created. File uploaded: %s", session_id, file.filename)
    return {"session_id": session_id, "filename": file.filename}


@router.post("/{session_id}/analyze", summary="Run analysis agents")
async def analyze_dataset(session_id: str):
    """Run Profiler, Schema Validator, and Anomaly Detector."""
    path = get_session_path(session_id)
    df = pd.read_csv(os.path.join(path, "original.csv"))

    # 1. Profiler
    profiler = ProfilerAgent()
    profiler_report = profiler.profile(df)
    save_json(os.path.join(path, "profiler_report.json"), profiler_report)

    # 2. Schema (auto-infer)
    schema = infer_schema(df)
    save_json(os.path.join(path, "schema.json"), schema)
    schema_validator = SchemaValidator()
    schema_report = schema_validator.validate(df, schema)
    save_json(os.path.join(path, "schema_report.json"), schema_report)

    # 3. Anomaly
    detector = AnomalyDetector()
    anomaly_report = detector.detect(df)
    save_json(os.path.join(path, "anomaly_report.json"), anomaly_report)

    return {
        "profiler": profiler_report.model_dump(),
        "schema": schema_report.model_dump(),
        "anomaly": anomaly_report.model_dump(),
    }


@router.post("/{session_id}/strategy", summary="Generate cleaning strategy")
async def generate_strategy(session_id: str, custom_provider_url: str = None):
    """Call the LLM Strategist to propose a cleaning strategy."""
    path = get_session_path(session_id)
    
    try:
        p_report = load_json(os.path.join(path, "profiler_report.json"))
        s_report = load_json(os.path.join(path, "schema_report.json"))
        a_report = load_json(os.path.join(path, "anomaly_report.json"))
    except HTTPException:
        raise HTTPException(status_code=400, detail="Run analysis first.")

    from agent.strategist.models import StrategistConfig
    
    config = StrategistConfig(
        endpoint_url=custom_provider_url or "http://localhost:11434/api/generate",
        model_name="llama3"
    )
    provider = OllamaProvider(config=config)
    strategist = StrategistAgent(provider=provider)
    
    try:
        strategy = strategist.generate_strategy(
            profiler_report=p_report,
            schema_report=s_report,
            anomaly_report=a_report,
        )
    except Exception as e:
        logger.error("LLM failure: %s", e)
        raise HTTPException(status_code=502, detail=f"LLM Generation failed: {str(e)}")

    save_json(os.path.join(path, "strategy_raw.json"), strategy)
    return strategy.model_dump()


@router.post("/{session_id}/validate-strategy", summary="Validate and apply strategy")
async def validate_strategy(session_id: str, request: StrategyApprovalRequest):
    """
    Accept the user-approved strategy actions, validate them deterministically,
    and save the ValidatedCleaningStrategy.
    """
    path = get_session_path(session_id)
    df = pd.read_csv(os.path.join(path, "original.csv"))

    known_columns = set(df.columns)
    
    try:
        p_report = load_json(os.path.join(path, "profiler_report.json"))
        column_types = {col["name"]: col["inferred_type"] for col in p_report["columns"]}
    except Exception:
        # Fallback to crude dtype mapping if profiler report is missing
        def _map_dtype(d):
            if "float" in d: return "numeric_float"
            if "int" in d: return "numeric_int"
            return "categorical"
        column_types = {col: _map_dtype(str(df[col].dtype)) for col in df.columns}
        
    total_row_count = len(df)
    validator = StrategyValidator(
        known_columns=known_columns,
        column_types=column_types,
        total_row_count=total_row_count
    )
    from agent.strategist.models import CleaningStrategy
    raw_strategy = CleaningStrategy(actions=request.actions)
    
    validated = validator.validate(raw_strategy)
    save_json(os.path.join(path, "strategy_validated.json"), validated)

    if not validated.is_valid:
        raise HTTPException(
            status_code=400, 
            detail={"message": "Strategy validation failed", "violations": [v.model_dump() for v in validated.violations]}
        )

    return validated.model_dump()


@router.post("/{session_id}/execute", summary="Execute cleaning strategy")
async def execute_strategy(session_id: str):
    """Run the deterministic Executor on the dataset using the Validated strategy."""
    path = get_session_path(session_id)
    
    try:
        validated_dict = load_json(os.path.join(path, "strategy_validated.json"))
        validated = ValidatedCleaningStrategy(**validated_dict)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Validate strategy first.")

    if not validated.is_valid:
        raise HTTPException(status_code=400, detail="Cannot execute an invalid strategy.")

    df = pd.read_csv(os.path.join(path, "original.csv"))
    
    executor = ExecutorAgent()
    cleaned_df, result = executor.execute(df, validated)

    # Save outputs
    cleaned_df.to_csv(os.path.join(path, "cleaned.csv"), index=False)
    save_json(os.path.join(path, "execution_result.json"), result)

    return result.model_dump()


@router.post("/{session_id}/validate-quality", summary="Post-cleaning validation")
async def validate_quality(session_id: str):
    """Run the Quality Assessor on before and after datasets."""
    path = get_session_path(session_id)

    try:
        df_before = pd.read_csv(os.path.join(path, "original.csv"))
        df_after = pd.read_csv(os.path.join(path, "cleaned.csv"))
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Missing original or cleaned dataset.")

    schema_dict = load_json(os.path.join(path, "schema.json"))
    expected_dtypes = {col: rule.get("expected_dtype", "object") for col, rule in schema_dict.get("columns", {}).items()}
    allowed_cats = {col: rule["allowed_values"] for col, rule in schema_dict.get("columns", {}).items() if rule.get("allowed_values")}

    assessor = QualityAssessor()
    report = assessor.assess(df_before, df_after, expected_dtypes, allowed_cats)
    
    save_json(os.path.join(path, "quality_report.json"), report)
    return report.model_dump()


@router.get("/{session_id}/download", summary="Download cleaned dataset")
async def download_cleaned(session_id: str):
    """Download the final cleaned CSV."""
    path = get_session_path(session_id)
    file_path = os.path.join(path, "cleaned.csv")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Cleaned dataset not found.")

    return FileResponse(
        file_path,
        media_type="text/csv",
        filename="cleaned_dataset.csv"
    )
