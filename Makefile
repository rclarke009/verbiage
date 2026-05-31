# Faithfulness eval harness. Brings up an ephemeral pgvector DB, seeds the frozen
# corpus, runs the eval, and tears the DB down. Requires Docker plus an LLM backend
# (OPENAI_API_KEY or a running Ollama) and an embedding backend / warm cache.

# --env-file /dev/null: the eval stack needs nothing from the repo .env, and skipping
# it avoids docker compose interpolation warnings from $-containing secrets in .env.
COMPOSE_EVAL := docker compose --env-file /dev/null -f docker-compose.eval.yml
EVAL_DB_URL  := postgresql://postgres:postgres@localhost:5433/verbiage_eval
EVAL_ENV     := VERBIAGE_EVAL=1 EVAL_DATABASE_URL=$(EVAL_DB_URL)

.PHONY: eval eval-full eval-up eval-down eval-warm-cache

# Fast gate (local NLI judge) -- run this after every tweak.
# Run the suite, ALWAYS tear the DB down, then exit with the suite's real status
# (all in one shell so the exit code propagates -- important for CI gating).
eval: eval-up
	@$(EVAL_ENV) python -m pytest -m eval_fast tests/eval -s; status=$$?; $(MAKE) eval-down; exit $$status

# Deep gate (OpenAI LLM-as-judge) -- nightly / manual.
eval-full: eval-up
	@$(EVAL_ENV) python -m pytest -m eval_full tests/eval -s; status=$$?; $(MAKE) eval-down; exit $$status

eval-up:
	-$(COMPOSE_EVAL) down -v --remove-orphans 2>/dev/null || true
	$(COMPOSE_EVAL) up -d --wait

eval-down:
	$(COMPOSE_EVAL) down -v

# Re-seed once against live backends to (re)populate tests/eval/embeddings_cache.json,
# then commit the cache so future runs are deterministic and offline.
eval-warm-cache: eval-up
	@$(EVAL_ENV) python -m tests.eval.seed; status=$$?; $(MAKE) eval-down; exit $$status
