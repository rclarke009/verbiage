---
name: Citations and report links
overview: Add optional stored `source_url` per document at ingest, derive Google Doc URLs for Drive ingests, join document metadata in retrieval, extend API responses, and show clickable "open report" links next to each cited source. Clarify in UX that links are as-of ingest (Drive file ids are stable; trashed/deleted files break the link; uploads need an explicit URL if you want a link).
todos:
  - id: migration-source-url
    content: Add `documents.source_url` migration; plumb `insert_document` + `ingest_text` + ingest APIs (incl. optional field on IngestRequest and PDF form)
    status: completed
  - id: drive-and-fallback
    content: Set Google Doc URL on Drive ingest; add COALESCE/derive for legacy `google_drive` rows in read path
    status: completed
  - id: retrieval-join-ask
    content: JOIN documents in `retrieve_top_k_pg`, extend RetrievedChunk, pass `user_id` in `/ask`, enrich LLM context blocks with title+link
    status: completed
  - id: documents-list-ui
    content: Expose `source_url` on DocumentSummary; render Open links in ask mentions + optional drawer
    status: completed
isProject: false
---

# Citations with links to full reports

## Your assumption (staleness)

- **Google Drive:** Ingest [uses the Drive file id as `doc_id`](app/drive_client.py) (`doc_id=file_id`). The open URL is stable for the **same** file: `https://docs.google.com/document/d/{fileId}/edit`. **Moving** a file between folders in Drive does **not** change the id, so the link usually stays valid. It can break if the file was **deleted**, **trashed**, or the user is **not allowed** to open it anymore.
- **PDFs / pasted text:** There is no natural URL unless the user (or client) provides one at ingest time. **Optional `source_url`** on ingest covers SharePoint, S3, presigned links, or internal wikis.

## Design

1. **Schema**  
   - Add nullable `source_url TEXT` on `documents` ([existing columns](supabase/migrations/20250302000000_phase1_schema.sql): `doc_id`, `title`, `source`, `created_at`, plus later `user_id`, `source_modified_at`).  
   - New Supabase migration under `supabase/migrations/`.

2. **Ingest: populate `source_url`**
   - Extend [`insert_document`](app/db.py) and [`ingest_text`](app/main.py) with optional `source_url: str | None = None`.
   - **Google Drive** ([`ingest_text` from `/ingest/google-drive`](app/main.py)): set `source_url` to `https://docs.google.com/document/d/{doc_id}/edit` for each ingested Google Doc (matches current behavior: [only `application/vnd.google-apps.document`](app/drive_client.py)).
   - **`POST /ingest` ([`IngestRequest`](app/models.py))** and **`POST /ingest/file`**: add optional `source_url` (JSON field + multipart `Form` field) so PDF/text workflows can store a report link when available.
   - **Backfill behavior (no re-ingest required):** at **read** time, if `source_url` is null and `source == "google_drive"`, **derive** the same Docs URL from `doc_id`. That way older rows still get a link in the API/UI without a data migration. Stored `source_url` wins when set (e.g. future support for other Drive file types with different URL patterns).

3. **List documents**  
   - Add `source_url` to [`list_documents`](app/db.py) / tuple unpacking, [`DocumentSummary`](app/models.py), and [`GET /documents`](app/main.py) so the drawer can show “Open” when a URL exists.

4. **Ask / “citations”**  
   - Extend [`retrieve_top_k_pg`](app/db.py) to `JOIN documents d` (both branches: with and without `user_id` filter) and select `d.title`, `d.source`, `d.source_url` (or compute effective URL in SQL with `COALESCE` for Drive, or in Python after fetch).  
   - Extend [`RetrievedChunk`](app/models.py) with optional fields, e.g. `document_title`, `source`, `source_url` (or a nested small object; flat is fine for the UI).  
   - Update [`retrieval.py`](app/retrieval.py) to map new columns into `RetrievedChunk`. In-memory path can leave new fields `None` or add a small doc metadata lookup.  
   - **LLM context** in [`/ask`](app/main.py): include **title** and **resolved link** in each block (e.g. after `doc_id`) so the model can refer to “the report” by name. Keep the existing “answer from context only” rule.  
   - **Scoping:** pass the authenticated `user_id` into `retrieve_top_k` in `/ask` (replace `user_id=None`) so retrieval matches [RLS/tenant intent](app/db.py) and joined `documents` rows are correct. This is a one-line fix in the same change.

5. **UI** ([`static/index.html`](static/index.html) Ask panel, “Where it’s mentioned”)  
   - For each document group, show **title** (or `doc_id` fallback) and, when `source_url` (or derived) is present, a safe **`<a href="..." target="_blank" rel="noopener noreferrer">Open full report</a>`** (use existing `escapeHtml` for display text; URL must be validated or only allow `https:` to avoid `javascript:` issues).  
   - Short footnote: “Link is from when the document was ingested; if the file was removed or you lost access, open the report from your Drive or files.” (optional, single line in UI copy).

6. **What we are *not* doing in v1 (unless you want to expand the plan)**  
   - **Inline numbered citations** in the model answer (e.g. `[1]`) with strict alignment to chunk order — can be a follow-up (prompt + optional `citations: [{ref, chunk_id}]` in response).  
   - **Deep links to a specific PDF page** — would need page/offset metadata not currently modeled.

## Files to touch (concise)

| Area | Files |
|------|--------|
| DB | New migration; [`app/db.py`](app/db.py) (`insert_document`, `list_documents`, `retrieve_top_k_pg`) |
| API | [`app/models.py`](app/models.py), [`app/main.py`](app/main.py) (ingest routes, `ingest_text`, `/documents`, `/ask` prompt) |
| Retrieval | [`app/retrieval.py`](app/retrieval.py) |
| UI | [`static/index.html`](static/index.html) (ask mentions + optional Documents drawer link column) |

## Test plan (lightweight)

- Ingest a Drive doc, ask a question, confirm JSON `top_chunks[].source_url` (or derived) and that the UI link opens the Doc.  
- Ingest a PDF with `source_url` set, confirm link appears.  
- Ingest without URL, confirm no broken link, snippets still show.
