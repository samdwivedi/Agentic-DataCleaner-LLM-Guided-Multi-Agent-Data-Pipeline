import logging
import os
from contextlib import asynccontextmanager

import app.persistence.models  # Important: Register models before create_all
from app.api.routes import datasets
from app.config.logging import setup_logging
from app.persistence.database import Base, engine
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["20/minute"])


# ── Security: Request size limiter ────────────────────────────────────────────
MAX_REQUEST_BODY_BYTES = 55 * 1024 * 1024  # 55 MB (slightly above the 50 MB CSV limit)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with bodies larger than MAX_REQUEST_BODY_BYTES."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
            return Response(
                content='{"detail":"Request body too large"}',
                status_code=413,
                media_type="application/json",
            )
        return await call_next(request)


# ── Security: Response headers ────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security-related response headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


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
    lifespan=lifespan,
)

# Register SlowAPI
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS: Restrict to configured origins ──────────────────────────────────────
# In production, set CORS_ORIGINS="https://your-domain.com,https://app.your-domain.com"
_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)

app.include_router(datasets.router)

from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = logging.getLogger(__name__)
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.get("/health", summary="Health check endpoint")
async def health():
    return {"status": "healthy"}
