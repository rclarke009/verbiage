# Verbiage: RAG API + web UI. Run with docker-compose (app + Postgres/pgvector).
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (app/, static/, etc.)
COPY app/ ./app/
COPY static/ ./static/

# Non-root user (optional but good practice)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
