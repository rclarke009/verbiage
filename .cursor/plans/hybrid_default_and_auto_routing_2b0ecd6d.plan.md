---
name: hybrid default and auto routing
overview: Make hybrid the default retrieval mode for the API (matching the README), and add an opt-in "auto" mode that adaptively routes each query to lexical or hybrid based on its shape.
todos:
  - id: default-hybrid
    content: In app/models.py, change AskRequest.retrieval_mode default to 'hybrid' and add 'auto' to the Literal + update description
    status: completed
  - id: auto-heuristic
    content: Add resolve_auto_mode(question) pure function to app/retrieval.py (lexical for short/quoted lookups, hybrid otherwise)
    status: completed
  - id: wire-dispatch
    content: In app/main.py _retrieve_for_ask, resolve 'auto' to a concrete mode before dispatch and import resolve_auto_mode
    status: completed
  - id: docs
    content: Update README.md to state hybrid is the default and document the auto adaptive option
    status: completed
  - id: tests
    content: Add tests for resolve_auto_mode, auto dispatch routing, and the new hybrid default
    status: completed
isProject: false
---

# Make hybrid the default + add adaptive "auto" routing

## Problem
The README sells hybrid (RRF) search as the headline feature, but the backend API default is `vector`. The SPA already sends `hybrid` (`useStreamingAsk(..., retrievalMode = 'hybrid')` in [frontend/src/hooks/useStreamingAsk.ts](frontend/src/hooks/useStreamingAsk.ts)), so the gap only affects direct API callers (curl, `/docs`, scripts). We'll close the gap and add an opt-in adaptive mode.

## Changes

### 1. Default to hybrid + add `auto` to the API contract
In [app/models.py](app/models.py) (line 65-68), update `AskRequest.retrieval_mode`:
- Add `"auto"` to the `Literal`: `Literal["vector", "lexical", "hybrid", "auto"]`.
- Change `default="vector"` to `default="hybrid"`.
- Update the description to document `auto` ("adaptive: routes per-query to lexical or hybrid").

### 2. Adaptive routing heuristic (pure function)
Add `resolve_auto_mode(question: str) -> Literal["vector", "lexical", "hybrid"]` to [app/retrieval.py](app/retrieval.py). Conservative policy (defensible for the storm-report domain where hybrid already dominates pure vector per the README):
- Returns `"lexical"` for short exact-term / identifier-style lookups — e.g. a quoted phrase present, or `<= 2` whitespace tokens (queries like `"torn shingles"`, `WY-2024`).
- Returns `"hybrid"` for everything else (natural-language / conceptual questions).
- Intentionally never returns pure `"vector"` (hybrid subsumes it on recall). This keeps the heuristic safe; can be expanded later if we want vector-only for purely conceptual queries.

### 3. Wire `auto` into the dispatch
In `_retrieve_for_ask` ([app/main.py](app/main.py) line 786-830), resolve `auto` at the top before the existing `if mode == ...` branches:

```python
mode = ask_request.retrieval_mode
if mode == "auto":
    mode = resolve_auto_mode(ask_request.question)
```

The existing `hybrid`/`lexical`/vector branches then run unchanged, and the correct mode-specific metrics (`record_hybrid_scores` / `record_lexical_scores` / `record_retrieval_scores`) fire based on the resolved mode. Import `resolve_auto_mode` alongside the other retrieval imports.

Note: embedding currently runs before retrieval in both `/ask` and `/ask/stream`, so `auto -> lexical` will still compute a (now unused) query vector. This is acceptable for v1; a later optimization could short-circuit the embed when the resolved mode is lexical.

### 4. Docs
Update [README.md](README.md) to state hybrid is the default retrieval mode and mention the `auto` adaptive option (e.g. in "Key Features" / "Technical Decisions" near the existing hybrid bullets, lines 23 and 143).

## Tests
[tests/test_retrieval.py](tests/test_retrieval.py) already constructs `AskRequest(..., retrieval_mode=...)` explicitly, so the default change won't break existing routing tests. Add:
- Unit tests for `resolve_auto_mode`: short/quoted query -> `lexical`; multi-word natural-language question -> `hybrid`.
- A dispatch test mirroring `test_retrieve_for_ask_hybrid_mode` but with `retrieval_mode="auto"`, asserting it routes to the hybrid path for a normal question.
- Optionally a test asserting `AskRequest(question="q").retrieval_mode == "hybrid"` (locks in the new default).

## Out of scope
- No frontend changes (SPA already defaults to hybrid). A future follow-up could expose an `auto` toggle in the UI.
- No embed short-circuit for lexical/auto (noted above as a later optimization).