---
name: switch embeddings to openai
overview: Switch embeddings (and the chat LLM) from local Ollama to OpenAI by setting OPENAI_API_KEY in the environment. No code changes are required — the routing already exists in app/embeddings.py and app/llm_client.py.
todos: []
isProject: false
---

# Switch Embeddings (and LLM) from Ollama to OpenAI

## Why this fixes the error
The crash (`httpx.ConnectError: All connection attempts failed`) happens because on Render the app tries to reach Ollama at `http://localhost:11434`, which only exists on your laptop. In `.env`, `OPENAI_API_KEY` is commented out, so `HttpEmbedder` falls back to the Ollama path:

```50:61:app/embeddings.py
    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if self._use_openai:
            try:
                return await embed_texts_openai(texts)
            ...
        return await embed_texts_ollama(texts)   # <- localhost:11434 on Render
```

`_use_openai` is simply `bool(OPENAI_API_KEY) and not EMBED_LOCAL_ONLY` (`app/config.py`). So setting the key flips embeddings to OpenAI automatically. The same key also routes the chat LLM to OpenAI via `answer_with_context` in `app/llm_client.py` (confirmed desired).

## No code changes required
The OpenAI implementation already exists in [app/embeddings_openai.py](app/embeddings_openai.py) (`text-embedding-3-small`, `dimensions=768`) and matches the `vector(768)` DB column in [app/db.py](app/db.py), so no schema migration is needed.

## Steps (config / ops only)
- Set `OPENAI_API_KEY` on Render: Render dashboard -> the backend service -> Environment -> add `OPENAI_API_KEY=sk-...`, then save (triggers a redeploy).
- Update local [.env](.env): uncomment and set `OPENAI_API_KEY=sk-...` (around line 21) so local dev matches.
- Do NOT set `EMBED_FALLBACK_TO_LOCAL` or `LLM_FALLBACK_TO_LOCAL` to true on Render — fallback points at the unreachable localhost Ollama and would just re-introduce the connect error.
- Leave `EMBED_LOCAL_ONLY` unset/false (if it were true, the key is ignored for embeddings).
- Optionally set `LLM_OPENAI_MODEL` (defaults to `gpt-4o-mini`) if you want a different chat model.

## Verify
- After redeploy, hit `GET /health/deep` (DB + embed check) and confirm the embed check passes.
- Re-run the Google Drive ingest that previously failed; it should now reach the embedding stage successfully.

## Cons / things to know
- Cost: OpenAI charges per token. `text-embedding-3-small` is very cheap (~$0.02 per 1M tokens); the bigger cost is the chat LLM (`gpt-4o-mini`) now also being billed. Previously both were free on local Ollama.
- Data leaves your machine: document and query text are sent to OpenAI's API (privacy/compliance consideration).
- Network dependency + rate limits: requests now depend on OpenAI uptime and your account quota. The code already retries on 429/timeout (`EMBED_MAX_ATTEMPTS=3`).
- Coupling: one key switches both embeddings and the LLM. Decoupling (OpenAI embeddings but non-OpenAI LLM) would require a small code change — not in scope.
- Existing data: retrieval filters by `embedding_model`, so any docs previously embedded with `nomic-embed-text` would silently drop from search until re-indexed. You confirmed nothing important is indexed yet, so no migration is needed. If that changes, re-index via the existing `reindex_document` path.

## Pros
- Works on Render with zero infra to manage (no separate Ollama service).
- Same 768-dim vectors -> no DB migration.
- Higher-quality, consistent embeddings without hosting a model.