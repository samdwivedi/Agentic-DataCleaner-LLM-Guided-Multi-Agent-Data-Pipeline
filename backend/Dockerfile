FROM python:3.12-slim

# ── Security: Create non-root user ───────────────────────────────────────────
RUN groupadd --system appuser && \
    useradd --system --gid appuser --create-home appuser

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# ── Security: Switch to non-root user ────────────────────────────────────────
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
