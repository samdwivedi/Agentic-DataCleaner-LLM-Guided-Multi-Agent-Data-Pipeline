from sqlalchemy import Column, String, LargeBinary, JSON
from .database import Base

class PipelineSession(Base):
    __tablename__ = "pipeline_sessions"

    session_id = Column(String, primary_key=True, index=True)
    original_csv = Column(LargeBinary, nullable=False)
    cleaned_csv = Column(LargeBinary, nullable=True)
    
    profiler_report = Column(JSON, nullable=True)
    schema_report = Column(JSON, nullable=True)
    anomaly_report = Column(JSON, nullable=True)
    strategy_raw = Column(JSON, nullable=True)
    strategy_validated = Column(JSON, nullable=True)
    execution_result = Column(JSON, nullable=True)
    quality_report = Column(JSON, nullable=True)
