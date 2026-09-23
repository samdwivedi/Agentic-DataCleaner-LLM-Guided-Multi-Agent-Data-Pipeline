import logging
from contextlib import asynccontextmanager

import app.persistence.models  # Important: Register models before create_all
from app.api.routes import datasets
from app.config.logging import setup_logging
from app.persistence.database import Base, engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup global logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Initialize Database Tables
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized.")
    
    yield
    logger.info("Shutting down AI Data Cleaning Agent API")

app = FastAPI(
    title="AI Data Cleaning Agent API",
    version="1.0.0",
    description="Multi-agent system for automated data profiling, strategy generation, and deterministic execution.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router)

@app.get("/health", summary="Health check endpoint")
async def health():
    return {"status": "healthy"}
