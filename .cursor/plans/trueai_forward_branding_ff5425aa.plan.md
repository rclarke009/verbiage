---
name: TrueAI forward branding
overview: Update the React SPA and HTML document title so users see **TrueAI** instead of **Verbiage** / generic **frontend**, without renaming internal repo identifiers (DB name, log paths, localStorage keys) unless you explicitly want those aligned.
todos:
  - id: app-tsx-brand
    content: Replace both Verbiage h1 strings in frontend/src/App.tsx with TrueAI
    status: completed
  - id: index-title
    content: Set <title> in frontend/index.html to TrueAI (and rebuild static via npm run build:static when shipping)
    status: completed
  - id: optional-fastapi-title
    content: "Optional: pass title=\"TrueAI\" to FastAPI() in app/main.py for /docs"
    status: completed
  - id: optional-reference-copy
    content: "Optional: mirror App.tsx + index.html in files_for_reference/frontend if that tree stays in sync"
    status: completed
isProject: false
---

# Rebrand forward-facing UI to TrueAI

## Scope (what users actually see)

| Location | Current | Change |
|----------|---------|--------|
| [frontend/src/App.tsx](frontend/src/App.tsx) | `<h1>Verbiage</h1>` on the signed-out shell (line ~35) and signed-in header (line ~57) | Replace with **TrueAI** |
| [frontend/index.html](frontend/index.html) | `<title>frontend</title>` | Set to **TrueAI** (or **TrueAI — Document RAG** if you want a longer tab label) |

The tagline lines (*“Document RAG workspace — sign in to continue.”* / *“RAG on your ingested reports”*) can stay as-is unless you want product copy to mention TrueAI explicitly there too.

## Build / deploy path

Production uses Vite with `DEPLOY_STATIC=1`, which writes into [`static/`](static/) ([Dockerfile](Dockerfile) copies `/build/static` → `./static`). After editing `frontend/index.html`, run `npm run build:static` in `frontend/` (or your usual Docker build) so [`static/index.html`](static/index.html) picks up the new `<title>`. **Do not** hand-edit `static/index.html` long-term; it is build output.

## Optional “nice to have” (not required for basic branding)

- **Swagger UI (`/docs`)**: [`app/main.py`](app/main.py) uses `FastAPI(lifespan=lifespan)` with no `title`. You can add e.g. `FastAPI(title="TrueAI", lifespan=lifespan)` so the API docs banner matches the product name.
- **Reference tree**: If you keep [`files_for_reference/frontend/`](files_for_reference/frontend/) in sync with the real app, mirror the same `App.tsx` + `index.html` edits there.
- **LocalStorage key**: [`frontend/src/hooks/useStreamingAsk.ts`](frontend/src/hooks/useStreamingAsk.ts) uses `verbiage-chat-messages`. Renaming to something like `trueai-chat-messages` is *not* user-visible but would **clear existing users’ cached chat** in the browser unless you add a one-time migration. Default recommendation: **leave as-is** unless you care about internal naming consistency.

## Out of scope (unless you ask to expand)

- Repo folder name, `POSTGRES_DB`, default `verbiage.db`, log file `verbiage.log`, internal comments, and docs like [README.md](README.md) / [overview.md](overview.md) — these are not “forward facing” in the browser; changing them is a separate hygiene pass.

```mermaid
flowchart LR
  subgraph source [Source]
    FE_HTML[frontend/index.html title]
    FE_APP[frontend/src/App.tsx h1]
  end
  subgraph build [Build]
    Vite[vite build:static]
  end
  subgraph ship [Served]
    Static[static/index.html]
    API[FastAPI optional /docs title]
  end
  FE_HTML --> Vite
  FE_APP --> Vite
  Vite --> Static
```
