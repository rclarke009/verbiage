# Verbiage — Code Notes

Implementation decisions for ingest, extraction, and RAG.

---

## Data sources: PDF and .docx only

**Decision:** Ingest report text from **PDF** and **.docx** only. Do not support **.pages** for the pipeline.

**Rationale:**

- We have a PDF (or .docx) for every report; .pages is redundant for ingestion.
- **PDF / .docx** have mature Python libraries (pypdf, PyMuPDF, python-docx); **.pages** requires unzipping and parsing Apple’s XML with no standard library and possible format changes.
- One pipeline (PDF + .docx) is simpler to build and maintain.

**Libraries:**

- **PDF:** `pypdf` or `PyMuPDF` (fitz) for text extraction. For scanned/image PDFs, `pdf2image` + `pytesseract` (OCR) can be added when needed.
- **.docx:** `python-docx` — extract paragraphs/runs as plain text.

**Ingest-from-files flow:** Accept a path or list of paths (PDF and/or .docx); per file, extract full text (and optionally title/source from filename or metadata); run the same chunk → embed → store path as `POST /ingest`.

**PDF: data only, no structure.** The pipeline extracts plain text (all pages), then chunks, embeds, and stores. It does not preserve sections, tables, or formatting. Tools to grab specially formatted areas (e.g. tables, defined regions) and image extraction/OCR can be added when needed.

---

## Models

- **Production:** OpenAI for LLM and embeddings when `OPENAI_API_KEY` is set.
- **Local / privacy-sensitive:** **Llama 3.1 8B** via Ollama for text/RAG (`ollama run llama3.1:8b`; LLM client at `http://localhost:11434`).
- **Vision:** Claim-photo analysis is already in the Report Writer path. Broader image→report generation (e.g. LLaVA via Ollama) remains a natural extension — same Ollama base URL, different model name and vision request shape.

Config for embed/LLM lives in `app/config.py` (see `.env.example`). Ask grounding prompts live with the ask handlers / prompt builders in `app/`.

---

## Chunking strategy for reports

**Decision:** Paragraph-first hybrid chunking (default strategy `paragraph`).

- **Normalize** line endings; split on blank lines into paragraphs.
- **Section headers** detected via numbered lines (`1. Overview`), ALL CAPS short lines, and title-case headings; label attached to following chunks as `[Section: …]` prefix and `chunks.section_label`.
- **Merge** paragraphs up to **1200** characters with **150** overlap (defaults on `ChunkingOptions`).
- **Oversized paragraphs** split at sentence boundaries; legacy `chars` strategy remains for tests.
- **Breadcrumb v2 (index time):** After chunking, each chunk gets a document-level prefix before embed/store: `[Document: …]`, optional `[Source: …]`, optional `[File: …]` (filename only when it differs from the display title). Section labels remain as `[Section: …]` inside chunk body. Offsets still refer to original `full_text`. Re-run **`POST /documents/{doc_id}/reindex`** (or bulk reindex) after deploying to refresh existing chunks.

**Canonical text:** `documents.full_text` in Supabase Postgres stores extracted text for re-chunk/re-embed via `POST /documents/{doc_id}/reindex` without re-uploading PDFs or re-exporting Drive.

**Metadata on `documents`:** `source_filename`, `source_url`, `chunking_config` (JSON), `embedding_model`. Retrieval filters `embeddings.model` to the active embedder so mixed-model indexes do not pollute search.
