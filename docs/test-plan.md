# Test plan — lab sheet

Clipboard for **what** we test, **when**, **how**, and **what number to write down**.

- How to run the commands: [setup_and_testing.md](../setup_and_testing.md)
- Why retrieval metrics look like this: [retrieval-eval.md](retrieval-eval.md)
- Why NLI / refusal / live proxies: [faithfulness-and-rag-metrics-walkthrough.md](faithfulness-and-rag-metrics-walkthrough.md)

Fill the header, run the experiment, copy numbers from the printed scoreboard into the blanks. Duplicate the [run log](#run-log-copy-this-block) at the bottom for each session.

```
Date: __________   Who: __________   What I changed: __________
```

---

## When to run what

GitHub CI does **not** run `make eval`. The eval gate is local (every tweak) and on `git push` if Docker is up.

```mermaid
flowchart TD
  commit["git commit"] --> precommit["pre-commit: pytest + frontend if frontend/ changed"]
  push["git push"] --> prepush["pre-push: make eval if Docker is up"]
  pr["PR / push to main"] --> ci["GitHub CI: pytest + frontend lint/test/build"]
  tweak["after a retrieval or prompt tweak"] --> evalFast["make eval"]
  corpus["after corpus / chunking / embed model change"] --> warm["make eval-warm-cache then make eval"]
  nightly["nightly or before a release"] --> evalFull["make eval-full"]
  optional["when judging the reranker"] --> rerank["make eval-retrieval-rerank"]
```

| When | Command | Experiments |
| --- | --- | --- |
| Every `git commit` | hooks run `pytest`; frontend only if `frontend/` changed | A |
| Every PR / push to `main` | GitHub Actions | A |
| Every retrieval or prompt tweak | `make eval` | B + C + D |
| Every `git push` (Docker up) | `make eval` via pre-push | B + C + D |
| Corpus / chunking / embed model change | `make eval-warm-cache` then `make eval` | B + C + D |
| Nightly or before a release | `make eval-full` | C (LLM judge) |
| Optional: reranker vs slice | `make eval-retrieval-rerank` | E |

---

## A. Did the code still work? (unit + frontend)

1. **Question** — Did a code change break routing, APIs, or the SPA without needing a real database?
2. **When** — Every `git commit` ([`.githooks/pre-commit`](../.githooks/pre-commit)). Every PR ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)). Locally, frontend lint / typecheck / Vitest run only when the commit touches `frontend/`. CI always runs them.
3. **How**

```bash
PYTHONPATH=. pytest tests/ -q
cd frontend && npm test
```

CI also runs `npm run lint`, `npm run typecheck`, and `npm run build`.

4. **Expected** — All tests pass. `tests/eval/` is skipped unless `VERBIAGE_EVAL=1`.
5. **Needs** — Project venv and deps. **No Docker. No LLM.**

**What this covers** (file list in [setup_and_testing.md](../setup_and_testing.md)): RRF / `auto` routing / cosine gate; reranker pool-widening; SSE `POST /ask/stream` contract; API smokes; indexing; Drive folder parsing; SPA stream parsing.

**Actual**

```
pytest:  ______ passed / ______ failed
vitest:  ______
```

---

## B. Did we find the right reports? (retrieval)

1. **Question** — Did gold reports enter the first-pass pool (`P=20`), and did the right ones survive into the prompt (`k=3`)?
2. **When** — Every tweak and every push (`make eval` includes `eval_fast` retrieval). **Not in CI.**
3. **How** — `make eval` (retrieval + faithfulness). Retrieval only (Docker + cache, **no LLM**):

```bash
make eval-up
VERBIAGE_EVAL=1 EVAL_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/verbiage_eval \
  pytest -m eval_fast tests/eval/test_retrieval.py -s
make eval-down
```

4. **Expected** (from [`tests/eval/test_retrieval.py`](../tests/eval/test_retrieval.py)):

| Row type | Pass bar |
| --- | --- |
| Every **answerable** gold | **recall@pool = 1.0** on `auto` |
| `answerable_single` | **recall@k = 1.0** |
| `answerable_multi` | **hit@k = 1.0** (print full recall@k; `k=3` can be smaller than the gold set) |
| Cosine gate | Must **not** drop a grounded question |
| Mode ablation (vector / lexical / hybrid / auto) | **Printed, not gated** |

5. **Needs** — Docker on port **5433**, committed [`tests/eval/embeddings_cache.json`](../tests/eval/embeddings_cache.json). Gold: [`tests/eval/gold_questions.yaml`](../tests/eval/gold_questions.yaml) (~38 questions: address singles, jargon/hail, multi-doc, `nearby_storm`, unanswerable). Unanswerable rows have no `relevant_doc_ids` — skip them here; they belong in D.

Do **not** reprint every question id. Copy failed ids from `MYDEBUG -> retrieval scoreboard`. Address lookups are the easy rows (lexical is strong when the query names the street). The rows that justify hybrid + a wide pool are **hail / jargon**, **multi-doc**, and **nearby_storm**.

**Actual** — copy from the scoreboard. Recall numbers are only comparable against this frozen index.

```
n_docs: ______    n_chunks: ______    pool_k: ______

All recall@pool = 1.0?     [ ] yes  [ ] no     failed ids: ______
Singles recall@k = 1.0?    [ ] yes  [ ] no     failed ids: ______
Multi hit@k = 1.0?         [ ] yes  [ ] no     failed ids: ______
Gate blocked a grounded Q? [ ] no   [ ] yes    ids: ______

Ablation mean r@pool (optional, not a gate):
  vector ______   lexical ______   hybrid ______   auto ______
Ablation mean r@k:
  vector ______   lexical ______   hybrid ______   auto ______
```

If a row fails, check one: **never in pool** (low recall@pool) / **trimmed from prompt** (high pool, low @k) / **gate blocked**.

---

## C. Did the answer stick to the sources? (faithfulness)

1. **Question** — Is every claim in the generated answer supported by the context that was actually retrieved?
2. **When** — Same `make eval` as B. Faithfulness needs an LLM; retrieval does not. Deeper judge: nightly or before a release.
3. **How** — `make eval` → local NliJudge. `make eval-full` → OpenAI LLM-as-judge (`OPENAI_API_KEY`).
4. **Expected** — `FAST_MIN_FAITHFULNESS = 1.0` in [`tests/eval/test_faithfulness.py`](../tests/eval/test_faithfulness.py). `must_mention` terms must appear in context (`ctx_ok`). A missing phrase is a **retriever** miss, not a generator miss.
5. **Needs** — Docker + embedding cache **and** an LLM (OpenAI or Ollama). First NLI run downloads `cross-encoder/nli-deberta-v3-base`.

**Actual** — copy from `MYDEBUG -> faithfulness scoreboard` (`faith`, `unsup`, `ctx_ok`).

```
All faith >= 1.0?   [ ] yes  [ ] no     failed ids: ______
ctx_ok on those?    [ ] yes  [ ] no     (no → retriever miss / must_mention)
unsupported claims: ______
```

---

## D. Did we refuse off-corpus only?

1. **Question** — Do unanswerable gold questions refuse, and do answerable ones still get through?
2. **When** — Same `make eval` as B (unanswerable gold in the faithfulness module).
3. **How** — `make eval`. No extra command.
4. **Expected** — Unanswerable → **refusal**. Answerable → **not** refused. A cosine-gate drop on a grounded question is already a fail in B.
5. **Needs** — Same as C (generation runs for the faithfulness suite).

**Actual**

```
Unanswerable refused?     [ ] yes  [ ] no     failed ids: ______
False refusal (answerable refused)?  [ ] no  [ ] yes     ids: ______
```

---

## E. Optional: is the reranker the bottleneck?

1. **Question** — On the same first-pass pool, does MiniLM rerank beat slice-to-`top_k`?
2. **When** — Not every tweak. When you are judging the reranker.
3. **How** — `make eval-retrieval-rerank` (loads ~100MB MiniLM; not in `make eval`).
4. **Expected** — Rerank must **not** change recall@pool (same first-pass list). Compare printed `slice@k` vs `rerank@k`.
5. **Needs** — Same as B, plus the cross-encoder download on first run.

Diagnosis (from [retrieval-eval.md](retrieval-eval.md)): **high pool + low @k** → trim / reranker. **Low pool** → first-pass (rerank cannot save it).

**Actual**

```
Pool recall unchanged?  [ ] yes  [ ] no
slice@k vs rerank@k (notes / failed ids): ______
```

---

## F. Live watching (not a lab — no gold)

Production traffic has **no** `relevant_doc_ids`. Do not write recall@pool here.

Watch instead: gate-pass rate, max cosine, lexical hit-rate, candidate-pool size, stage latency, embedding **model version**, index size. If live retrieval drops suddenly, check embedding model version first (different versions are different vector spaces). Details: [faithfulness-and-rag-metrics-walkthrough.md](faithfulness-and-rag-metrics-walkthrough.md).

---

## Run log (copy this block)

Duplicate per session. Fill from the scoreboards after the command finishes.

```
Date: ______   Who: ______   Change: ______
Command: [ ] pytest  [ ] make eval  [ ] make eval-full  [ ] make eval-retrieval-rerank  [ ] other: ______
n_docs: ______   n_chunks: ______

A Unit/frontend: [ ] pass  [ ] fail     pytest ______ / vitest ______

B Retrieval: [ ] pass  [ ] fail    failed ids: ______
  if fail, check one: [ ] never in pool  [ ] trimmed from prompt  [ ] gate blocked

C Faithfulness: [ ] pass  [ ] fail    failed ids: ______
  if fail, check one: [ ] missing must_mention  [ ] unsupported claim

D Refusal: [ ] pass  [ ] fail    failed ids: ______

E Rerank (optional): slice@k ______   rerank@k ______   pool unchanged? [ ] yes  [ ] no

Ablation means (optional): vector r@pool ______  lexical ______  hybrid ______  auto ______
Notes: ______
```
