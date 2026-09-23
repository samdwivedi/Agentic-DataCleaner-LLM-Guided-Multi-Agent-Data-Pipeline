"""
End-to-End Tests for the Complete Data Cleaning Pipeline.
"""

from __future__ import annotations

import io
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app as fastapi_app
from app.models.strategy import CleaningStrategy
from app.models.strategy_validator import ValidatedCleaningStrategy
from app.persistence.database import Base, get_db
from app.persistence.repository import SessionRepository
import app.persistence.models  # Register models

from sqlalchemy.pool import StaticPool

# Set up SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

fastapi_app.dependency_overrides[get_db] = override_get_db

# Create tables in the in-memory DB for tests
Base.metadata.create_all(bind=engine)

client = TestClient(fastapi_app)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    try:
        os.remove("test.db")
    except OSError:
        pass

@pytest.fixture
def synthetic_csv_content():
    """A dirty dataset for E2E testing."""
    return (
        "id,age,category\n"
        "1,25.0,A\n"
        "2,,B\n"         # Missing
        "3,30.0,X\n"     # Invalid category (we'll assume only A,B are allowed eventually)
        "4,400.0,A\n"    # Outlier
        "5,35.0,\n"      # Missing
        "6,26.0,B\n"
        "6,26.0,B\n"     # Duplicate
        "8,,A\n"
        "9,29.0,Y\n"
        "10,31.0,B\n"
    )

@pytest.fixture
def mock_strategy():
    """A valid strategy to mock the LLM output."""
    return CleaningStrategy(
        actions=[
            {
                "column": "age",
                "action": "median_imputation",
                "parameters": {},
                "reason": "Missing values.",
                "confidence": 0.95
            },
            {
                "column": "id",
                "action": "remove_duplicates",
                "parameters": {},
                "reason": "Duplicate rows found.",
                "confidence": 0.99
            },
            {
                "column": "age",
                "action": "cap_outliers",
                "parameters": {},
                "reason": "Extreme outlier detected.",
                "confidence": 0.90
            }
        ]
    )

# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPipelineEndToEnd:

    def test_full_happy_path(self, synthetic_csv_content, mock_strategy):
        # 1. Upload
        file_obj = io.BytesIO(synthetic_csv_content.encode("utf-8"))
        response = client.post(
            "/pipeline/upload", 
            files={"file": ("dirty.csv", file_obj, "text/csv")}
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        
        # 2. Analyze
        response = client.post(f"/pipeline/{session_id}/analyze")
        assert response.status_code == 200
        analysis = response.json()
        assert "profiler" in analysis
        assert "schema" in analysis
        assert "anomaly" in analysis

        # 3. Strategy (Mocked LLM)
        with patch("app.agents.strategist.agent.StrategistAgent.generate_strategy", return_value=mock_strategy):
            response = client.post(f"/pipeline/{session_id}/strategy")
            assert response.status_code == 200
            strategy_data = response.json()
            assert len(strategy_data["actions"]) == 3

        # 4. Validate Strategy
        response = client.post(
            f"/pipeline/{session_id}/validate-strategy", 
            json={"actions": strategy_data["actions"]}
        )
        assert response.status_code == 200
        validated_data = response.json()
        assert validated_data["is_valid"] is True

        # 5. Execute
        response = client.post(f"/pipeline/{session_id}/execute")
        assert response.status_code == 200
        execution_data = response.json()
        assert execution_data["successful_actions"] == 3

        # 6. Post-Validation
        response = client.post(f"/pipeline/{session_id}/validate-quality")
        assert response.status_code == 200
        quality_data = response.json()
        assert quality_data["is_successful"] is True
        assert quality_data["improvement"] > 0

        # 7. Download
        response = client.get(f"/pipeline/{session_id}/download")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        cleaned_csv = response.content.decode("utf-8")
        assert "400.0" not in cleaned_csv  # Outlier capped


    def test_ollama_unavailable(self, synthetic_csv_content):
        """Test #5: Ollama unavailable handles error cleanly."""
        file_obj = io.BytesIO(synthetic_csv_content.encode("utf-8"))
        session_id = client.post(
            "/pipeline/upload", files={"file": ("test.csv", file_obj, "text/csv")}
        ).json()["session_id"]
        client.post(f"/pipeline/{session_id}/analyze")

        # By default, hitting localhost on a random/bad port should fail
        response = client.post(f"/pipeline/{session_id}/strategy?custom_provider_url=http://localhost:59999")
        assert response.status_code == 502
        assert "LLM Generation failed" in response.json()["detail"]


    def test_dangerous_strategy(self, synthetic_csv_content):
        """Test #7: Validator catches dangerous strategy (dropping all rows)."""
        file_obj = io.BytesIO(synthetic_csv_content.encode("utf-8"))
        session_id = client.post(
            "/pipeline/upload", files={"file": ("test.csv", file_obj, "text/csv")}
        ).json()["session_id"]
        client.post(f"/pipeline/{session_id}/analyze")

        dangerous_actions = [{"column": "age", "action": "drop_column", "reason": "danger", "confidence": 0.9}] * 10
        # Pretend LLM outputted this and the user tried to validate it
        response = client.post(
            f"/pipeline/{session_id}/validate-strategy", 
            json={"actions": dangerous_actions}
        )
        assert response.status_code == 400
        assert "validation failed" in response.json()["detail"]["message"].lower()


    def test_executor_failure_recovery(self, synthetic_csv_content):
        """Test #8: Executor handles failing operation safely."""
        file_obj = io.BytesIO(synthetic_csv_content.encode("utf-8"))
        session_id = client.post(
            "/pipeline/upload", files={"file": ("test.csv", file_obj, "text/csv")}
        ).json()["session_id"]
        client.post(f"/pipeline/{session_id}/analyze")

        # Fake a validated strategy with a ghost column to trigger a failure
        actions = [
            {"column": "ghost", "action": "median_imputation", "reason": "test", "confidence": 0.9},
            {"column": "age", "action": "median_imputation", "reason": "test", "confidence": 0.9},
        ]
        
        # Override the normal validator check just to force this into the executor
        # We'll use patch to make it look like it's valid
        with patch("app.agents.strategy_validator.agent.StrategyValidator.validate") as mock_val:
            mock_val.return_value = ValidatedCleaningStrategy(
                is_valid=True,
                actions=actions,
                violations=[],
                original_action_count=2,
                validated_action_count=2
            )
            client.post(f"/pipeline/{session_id}/validate-strategy", json={"actions": actions})

        response = client.post(f"/pipeline/{session_id}/execute")
        assert response.status_code == 200
        res = response.json()
        assert res["failed_actions"] == 1
        assert res["successful_actions"] == 1


    def test_post_validation_failure(self, synthetic_csv_content):
        """Test #9: Post-validation flags failure if quality degrades."""
        file_obj = io.BytesIO(synthetic_csv_content.encode("utf-8"))
        session_id = client.post(
            "/pipeline/upload", files={"file": ("test.csv", file_obj, "text/csv")}
        ).json()["session_id"]
        client.post(f"/pipeline/{session_id}/analyze")

        worse_csv = (
            "id,age,category\n"
            ",,\n" * 10
        ).encode("utf-8")
        
        # Override DB directly
        db = TestingSessionLocal()
        repo = SessionRepository(db)
        repo.save_cleaned_csv(session_id, worse_csv)
        db.close()

        response = client.post(f"/pipeline/{session_id}/validate-quality")
        assert response.status_code == 200
        res = response.json()
        assert res["is_successful"] is False
        assert res["improvement"] < 0
        assert any(f["dimension"] == "score" for f in res["critical_failures"])


    def test_original_dataset_preservation(self, synthetic_csv_content):
        """Test #10: Original dataset is never modified."""
        file_obj = io.BytesIO(synthetic_csv_content.encode("utf-8"))
        session_id = client.post(
            "/pipeline/upload", files={"file": ("test.csv", file_obj, "text/csv")}
        ).json()["session_id"]
        
        db = TestingSessionLocal()
        repo = SessionRepository(db)
        original_before = repo.get_original_csv(session_id)
        db.close()

        # Run pipeline up to execute
        client.post(f"/pipeline/{session_id}/analyze")
        
        actions = [{"column": "age", "action": "median_imputation", "reason": "test", "confidence": 0.9}]
        client.post(f"/pipeline/{session_id}/validate-strategy", json={"actions": actions})
        client.post(f"/pipeline/{session_id}/execute")

        db = TestingSessionLocal()
        repo = SessionRepository(db)
        original_after = repo.get_original_csv(session_id)
        db.close()
            
        assert original_before == original_after
