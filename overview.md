# Verbiage — Overview

AI-powered verbiage for storm damage reports. Ingest past reports, then get overview and detailed-image copy suggested from similar cases.

**Slogan:** *From field notes to finished copy.*

---

## What It Does

- **Ingest** — Store storm damage reports (PDF, DOCX, text paste, or Google Drive). Chunk, embed, and index for retrieval; durable job queue for batch uploads.
- **Shared library** — List, filter, and manage ingested documents so the team sees one collaborative corpus.
- **Ask** — Describe the current case (symptom, damage type, location, etc.). The app retrieves similar past report text and returns grounded **overview** and **detailed image** verbiage with source citations — or refuses when retrieval is too weak.
- **Report Writer** — LangGraph workflow that drafts structured report sections from field notes, claim photos, and similar past reports (SSE streaming; optional human-in-the-loop).

Works “forward” (drafting from scratch) or “backward” (rewriting rough notes)—either way, AI turns rough input into report-ready verbiage.

---

## Architecture

- **Ingest** — Extract text → store canonical `full_text` → paragraph-first chunking → embeddings in Postgres (`documents`, `chunks`, `embeddings` with pgvector). Drive and large batches go through a Postgres-backed job queue.
- **Retrieval** — Adaptive routing (`auto`): short identifier/exact-term queries → lexical full-text; otherwise hybrid (vector + lexical) fused with Reciprocal Rank Fusion. Queries are normalized for embed/lexical before search. Optional cross-encoder rerank; pre-LLM relevance gate refuses off-corpus questions before any generation spend. Soft refuse may trigger one domain-phrase rewrite-and-retrieve.
- **Ask / Report Writer** — Grounded LLM generation with citations and validation; same relevance gate on both paths. Auth via Supabase JWT (closed signup).

Domain focus: storm damage reports and reusable inspection wording.

---

## Tech

- **Backend:** FastAPI, Pydantic v2, async LLM + embedding clients
- **Store / search:** PostgreSQL + pgvector (Supabase in production); hybrid retrieval + RRF; optional cross-encoder rerank
- **Frontend:** React + Vite SPA (TanStack Query)
- **Auth:** Supabase JWT; invite code or email allowlist
- **Data sources:** PDF and `.docx` (upload or Drive); text paste (see `code-notes.md`)
- **Models:** OpenAI in production; Ollama (e.g. Llama 3.1 8B) for local/dev. Vision analysis for claim photos is in use today; broader image→report generation remains a natural extension.

---

## Hosting

**Production app URL:** [https://rag-document-analysis-backend.onrender.com](https://rag-document-analysis-backend.onrender.com) (sign-in required)

More detail: [README.md](README.md).
