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
    TRANSFORMERS_OFFLINE=1

RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the cross-encoder reranker into HF_HOME at build time. Done with the
# Hub online here; runtime stays offline (env vars above) so it never re-fetches.
RUN HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

COPY app/ ./app/
COPY --from=frontend /build/static ./static/

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Honor Render's injected $PORT (falls back to 8000 locally).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
