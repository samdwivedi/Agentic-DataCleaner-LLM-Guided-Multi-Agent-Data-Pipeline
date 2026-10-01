from typing import Any

from sqlalchemy.orm import Session

from .models import PipelineSession

# ── Allowlist of valid report column names ────────────────────────────────────
_VALID_REPORT_TYPES = frozenset({
    "profiler_report",
    "schema_report",
    "anomaly_report",
    "strategy_raw",
    "strategy_validated",
    "execution_result",
    "quality_report",
})


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_session(self, session_id: str) -> PipelineSession:
        session = self.db.query(PipelineSession).filter(PipelineSession.session_id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found.")
        return session

    def create_session(self, session_id: str, original_csv_bytes: bytes) -> PipelineSession:
        db_session = PipelineSession(session_id=session_id, original_csv=original_csv_bytes)
        self.db.add(db_session)
        self.db.commit()
        self.db.refresh(db_session)
        return db_session

    def update_report(self, session_id: str, report_type: str, report_data: dict[str, Any]) -> None:
        """
        Updates one of the JSON report columns.
        report_type must be one of the allowed column names in _VALID_REPORT_TYPES.
        """
        if report_type not in _VALID_REPORT_TYPES:
            raise ValueError(
                f"Invalid report_type '{report_type}'. "
                f"Must be one of: {', '.join(sorted(_VALID_REPORT_TYPES))}"
            )
        db_session = self.get_session(session_id)
        setattr(db_session, report_type, report_data)
        self.db.commit()

    def get_report(self, session_id: str, report_type: str) -> dict[str, Any] | None:
        if report_type not in _VALID_REPORT_TYPES:
            raise ValueError(
                f"Invalid report_type '{report_type}'. "
                f"Must be one of: {', '.join(sorted(_VALID_REPORT_TYPES))}"
            )
        db_session = self.get_session(session_id)
        report = getattr(db_session, report_type)
        if report is None:
            raise FileNotFoundError(f"Report {report_type} not found for session {session_id}")
        return report

    def get_original_csv(self, session_id: str) -> bytes:
        db_session = self.get_session(session_id)
        return db_session.original_csv

    def save_cleaned_csv(self, session_id: str, cleaned_csv_bytes: bytes) -> None:
        db_session = self.get_session(session_id)
        db_session.cleaned_csv = cleaned_csv_bytes
        self.db.commit()

    def get_cleaned_csv(self, session_id: str) -> bytes:
        db_session = self.get_session(session_id)
        if not db_session.cleaned_csv:
            raise FileNotFoundError("Cleaned dataset not found.")
        return db_session.cleaned_csv
