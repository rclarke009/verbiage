# Verbiage: RAG API + SPA (Vite build → static/) + Postgres/pgvector.
FROM node:20-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build:static

FROM python:3.11-slim

WORKDIR /app

# Persisted HuggingFace cache: the reranker model is baked into the image below so
# cold starts load it from local disk instead of re-downloading from the HF Hub on
# every boot (which was slow and spiked memory/latency on the request path).
ENV HF_HOME=/app/hf-cache \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Skip ~2GB torch/sentence-transformers bake when RERANK_ENABLED=0 (prod + demo default).
# Rebuild with --build-arg SKIP_RERANK=0 if you enable reranking in production.
ARG SKIP_RERANK=1

RUN pip install --no-cache-dir --upgrade pip setuptools wheel
COPY requirements.txt .
# Install everything except sentence-transformers first (smaller, more reliable on Render).
RUN grep -v '^sentence-transformers' requirements.txt > /tmp/requirements-base.txt && \
    pip install --no-cache-dir -r /tmp/requirements-base.txt

# Optional reranker stack: heavy downloads often flake on free-tier builders (broken pipe).
RUN if [ "$SKIP_RERANK" != "1" ]; then \
      for attempt in 1 2 3; do \
        pip install --no-cache-dir sentence-transformers && break; \
        echo "MYDEBUG -> sentence-transformers install attempt $attempt failed, retrying..."; \
        sleep 20; \
      done && \
      HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"; \
    fi

COPY app/ ./app/
COPY --from=frontend /build/static ./static/

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Honor Render's injected $PORT (falls back to 8000 locally).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
