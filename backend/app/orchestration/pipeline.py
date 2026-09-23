import io
import json
import logging
import uuid
from typing import Any

import pandas as pd
from app.agents.anomaly_detector.agent import AnomalyDetector
from app.agents.executor.agent import ExecutorAgent
from app.agents.profiler.agent import ProfilerAgent
from app.agents.schema_validator.agent import (
    ColumnRule,
    SchemaValidator,
    ValidationSchema,
)
from app.agents.strategist.agent import StrategistAgent
from app.agents.strategy_validator.agent import StrategyValidator
from app.agents.validator.agent import QualityAssessor
from app.llm.providers import OllamaProvider
from app.models.strategy import CleaningStrategy, StrategistConfig
from app.models.strategy_validator import ValidatedCleaningStrategy
from app.persistence.repository import SessionRepository

logger = logging.getLogger(__name__)


def infer_schema(df: pd.DataFrame) -> ValidationSchema:
    columns = {}
    for col in df.columns:
        dtype = str(df[col].dtype)
        columns[col] = ColumnRule(
            expected_dtype=dtype,
            nullable=True,
        )
    return ValidationSchema(required_columns=list(df.columns), columns=columns)


class PipelineOrchestrator:
    
    @staticmethod
    def initialize_session(repo: SessionRepository, file_bytes: bytes) -> str:
        # Ensure it parses
        try:
            pd.read_csv(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(f"Invalid CSV: {e!s}")
            
        session_id = str(uuid.uuid4())
        repo.create_session(session_id, file_bytes)
        return session_id

    @staticmethod
    def analyze(repo: SessionRepository, session_id: str) -> dict[str, Any]:
        csv_bytes = repo.get_original_csv(session_id)
        df = pd.read_csv(io.BytesIO(csv_bytes))

        profiler = ProfilerAgent()
        profiler_report = profiler.profile(df)
        repo.update_report(session_id, "profiler_report", profiler_report.model_dump())

        schema = infer_schema(df)
        repo.update_report(session_id, "schema_report", schema.model_dump()) # Wait! This is validation schema, we want schema_report
        
        schema_validator = SchemaValidator()
        schema_report = schema_validator.validate(df, schema)
        repo.update_report(session_id, "schema_report", schema_report.model_dump())

        detector = AnomalyDetector()
        anomaly_report = detector.detect(df)
        repo.update_report(session_id, "anomaly_report", anomaly_report.model_dump())

        return {
            "profiler": profiler_report.model_dump(),
            "schema": schema_report.model_dump(),
            "anomaly": anomaly_report.model_dump(),
        }

    @staticmethod
    def generate_strategy(repo: SessionRepository, session_id: str, custom_provider_url: str = None) -> dict[str, Any]:
        p_report = repo.get_report(session_id, "profiler_report")
        s_report = repo.get_report(session_id, "schema_report")
        a_report = repo.get_report(session_id, "anomaly_report")

        config = StrategistConfig(
            endpoint_url=custom_provider_url or "http://localhost:11434/api/generate",
            model_name="llama3"
        )
        provider = OllamaProvider(config=config)
        strategist = StrategistAgent(provider=provider)
        
        strategy = strategist.generate_strategy(
            profiler_report=p_report,
            schema_report=s_report,
            anomaly_report=a_report,
        )
        
        repo.update_report(session_id, "strategy_raw", strategy.model_dump())
        return strategy.model_dump()

    @staticmethod
    def validate_strategy(repo: SessionRepository, session_id: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
        csv_bytes = repo.get_original_csv(session_id)
        df = pd.read_csv(io.BytesIO(csv_bytes))
        known_columns = set(df.columns)
        
        try:
            p_report = repo.get_report(session_id, "profiler_report")
            column_types = {col["name"]: col["inferred_type"] for col in p_report["columns"]}
        except Exception:
            def _map_dtype(d):
                if "float" in d: return "numeric_float"
                if "int" in d: return "numeric_int"
                return "categorical"
            column_types = {col: _map_dtype(str(df[col].dtype)) for col in df.columns}
            
        validator = StrategyValidator(
            known_columns=known_columns,
            column_types=column_types,
            total_row_count=len(df)
        )
        
        raw_strategy = CleaningStrategy(actions=actions)
        validated = validator.validate(raw_strategy)
        repo.update_report(session_id, "strategy_validated", validated.model_dump())
        
        if not validated.is_valid:
            raise ValueError(json.dumps([v.model_dump() for v in validated.violations]))
            
        return validated.model_dump()

    @staticmethod
    def execute_strategy(repo: SessionRepository, session_id: str) -> dict[str, Any]:
        validated_dict = repo.get_report(session_id, "strategy_validated")
        validated = ValidatedCleaningStrategy(**validated_dict)
        
        if not validated.is_valid:
            raise ValueError("Cannot execute an invalid strategy.")

        csv_bytes = repo.get_original_csv(session_id)
        df = pd.read_csv(io.BytesIO(csv_bytes))
        
        executor = ExecutorAgent()
        cleaned_df, result = executor.execute(df, validated)

        # Save CSV to memory buffer then to DB
        buf = io.BytesIO()
        cleaned_df.to_csv(buf, index=False)
        repo.save_cleaned_csv(session_id, buf.getvalue())
        
        repo.update_report(session_id, "execution_result", result.model_dump())
        
        return result.model_dump()

    @staticmethod
    def validate_quality(repo: SessionRepository, session_id: str) -> dict[str, Any]:
        csv_orig = repo.get_original_csv(session_id)
        df_before = pd.read_csv(io.BytesIO(csv_orig))
        
        csv_cleaned = repo.get_cleaned_csv(session_id)
        df_after = pd.read_csv(io.BytesIO(csv_cleaned))
        
        # We need the inferred schema for the quality assessor
        schema = infer_schema(df_before)
        schema_dict = schema.model_dump()
        expected_dtypes = {col: rule.get("expected_dtype", "object") for col, rule in schema_dict.get("columns", {}).items()}
        allowed_cats = {col: rule["allowed_values"] for col, rule in schema_dict.get("columns", {}).items() if rule.get("allowed_values")}

        assessor = QualityAssessor()
        report = assessor.assess(df_before, df_after, expected_dtypes, allowed_cats)
        repo.update_report(session_id, "quality_report", report.model_dump())
        
        return report.model_dump()
