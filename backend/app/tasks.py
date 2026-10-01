import logging
from typing import Any

from app.celery_app import celery_app
from app.orchestration.pipeline import PipelineOrchestrator
from app.persistence.database import SessionLocal
from app.persistence.repository import SessionRepository

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="analyze_task")
def analyze_task(self, session_id: str) -> dict[str, Any]:
    db = SessionLocal()
    repo = SessionRepository(db)
    try:
        return PipelineOrchestrator.analyze(repo, session_id)
    except Exception as e:
        logger.exception("Error in analyze_task")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="generate_strategy_task")
def generate_strategy_task(self, session_id: str) -> dict[str, Any]:
    db = SessionLocal()
    repo = SessionRepository(db)
    try:
        return PipelineOrchestrator.generate_strategy(repo, session_id)
    except Exception as e:
        logger.exception("Error in generate_strategy_task")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="validate_strategy_task")
def validate_strategy_task(self, session_id: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    db = SessionLocal()
    repo = SessionRepository(db)
    try:
        return PipelineOrchestrator.validate_strategy(repo, session_id, actions)
    except Exception as e:
        logger.exception("Error in validate_strategy_task")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="execute_strategy_task")
def execute_strategy_task(self, session_id: str) -> dict[str, Any]:
    db = SessionLocal()
    repo = SessionRepository(db)
    try:
        return PipelineOrchestrator.execute_strategy(repo, session_id)
    except Exception as e:
        logger.exception("Error in execute_strategy_task")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="validate_quality_task")
def validate_quality_task(self, session_id: str) -> dict[str, Any]:
    db = SessionLocal()
    repo = SessionRepository(db)
    try:
        return PipelineOrchestrator.validate_quality(repo, session_id)
    except Exception as e:
        logger.exception("Error in validate_quality_task")
        raise
    finally:
        db.close()
