# Retrieval eval — recall@pool, recall@k, and why we chose them

Internal reference for the **labeled retrieval suite**: what we measure, why those metrics instead of nearby alternatives, and interview Q→A. Generation-side faithfulness stays in [faithfulness-and-rag-metrics-walkthrough.md](faithfulness-and-rag-metrics-walkthrough.md). How to run: [setup_and_testing.md](../setup_and_testing.md). Lab sheet (what / when / how / fill-in results): [test-plan.md](test-plan.md).

---

## 0. The story in one paragraph

A retrieve-then-rerank pipeline has two different “did we find it?” questions. **Recall@pool** asks whether gold reports appeared in the **first-pass candidate set** (width \(P\), production-with-rerank \(P = \max(4k, 20)\)). **Recall@k** asks whether they survived the trim (or rerank) into the **prompt**. The reranker can only reorder what first-pass retrieved; pool recall is the ceiling. We score **documents**, not chunk IDs, on a frozen 15-report corpus, without an LLM. Faithfulness still judges the generated answer.

---

## 1. What we measure

Gold lives in [`tests/eval/gold_questions.yaml`](../tests/eval/gold_questions.yaml): `relevant_doc_ids` are filename stems from [`app/demo_corpus/`](../app/demo_corpus/). Metrics are computed on **first-occurrence unique `doc_id`s** (two chunks from the same report count as one hit).

| Metric | Cutoff | Meaning |
| --- | --- | --- |
| **Recall@pool** | First-pass list of size \(P=20\) | Fraction of gold reports that entered the candidate pool. |
| **Recall@k** | Prompt set, default \(k=3\) | Fraction of gold reports that made the prompt. |
| **Hit@k** | Prompt set | 1 if *any* gold report is in the prompt. |
| **MRR** | Prompt set | \(1 /\) rank of the first gold report (0 if none). |

Unanswerable gold has no `relevant_doc_ids`. Those rows are **undefined** (not zero). Refusal tests already own them.

`nearby_storm` questions use the structured geo path. There is no RRF pool to widen; pool and prompt are the same returned neighbor list.

### Gates (`make eval` / `eval_fast`)

- Every **answerable** question: **recall@pool = 1.0** on the production `auto` path (every gold report must enter \(P\)).
- **answerable_single**: **recall@k = 1.0** (the one right report must be in the prompt).
- **answerable_multi**: **hit@k = 1.0** (at least one gold report in the prompt). Full recall@k is printed; \(k=3\) can be smaller than the gold set.

Vector / lexical / hybrid vs auto is an **ablation table**, not a second gate.

Optional MiniLM comparison: `make eval-retrieval-rerank` (`eval_retrieval_rerank`). Same pool, slice vs cross-encoder; not in the every-tweak gate (avoids the ~100MB model).

Corpus `n_docs` / `n_chunks` print on the scoreboard. Recall numbers are only comparable against that frozen index.

---

## 2. Why these choices (and what we rejected)

### Why labeled recall, not `must_mention`?

`must_mention` is a **term-in-context proxy**. It still runs on the faithfulness path so a missing phrase is blamed on retrieval, not NLI. It cannot tell “right words, wrong property.” Labeled `relevant_doc_ids` can.

We **kept** `must_mention`. Complementary, not a substitute.

### Why documents, not chunk IDs?

Chunk IDs are `{doc_id}:{index}` and **break on rechunk**. The product failure mode is usually the wrong report. Document IDs are filename stems and stay stable when paragraph boundaries move.

Chunk-level gold is worth adding later if we need “right report, wrong paragraph.” It should not be the blocking gate until labels can survive chunking changes (content hashes, not indexes).

### Why force \(P=20\) even when the reranker is off?

Eval historically called `_retrieve_for_ask(..., reranker=None)`, which sets `pool_k == top_k`. Then recall@pool **equals** recall@k and you cannot tell “never retrieved” from “retrieved then trimmed.”

Eval now passes `candidate_k=max(top_k*4, 20)`. Production Ask is unchanged: no reranker still means no widening. `RetrieveOutcome.pool_chunks` is the pre-rerank / pre-slice list.

### Why not RAGAS / LLM “context recall” as the primary retrieval metric?

LLM-as-judge context recall asks “does this context contain enough to answer?” It is useful when you **lack** labels. It is also slow, billed, and noisy. We already pay an NLI judge for **generation** faithfulness. Retrieval gets **deterministic labels** on a 12-doc corpus we control.

Use an LLM retrieval judge if we add unlabeled production sampling. Not as the regression gate.

### Why not graded nDCG as a gate?

nDCG needs **graded** relevance (0/1/2). We have binary labels. Binary nDCG is well-defined but adds little over recall@k + MRR until we label “related but not required” reports. Especially useful **after** we turn the reranker on in eval.

### Why MRR is secondary

MRR ignores everything after the first gold hit. Multi-report questions (`answerable_multi`) are exactly when that is the wrong summary. We still print it; we do not gate on it.

### Why this stays offline (not Prometheus)

Recall needs gold. Live traffic has none. Production watches **proxies**: gate-pass rate, max cosine, lexical hit-rate, candidate-pool size, stage latency, embedding model version, index size. A recall@pool time series without a frozen labeled set is fiction.

### Why the interesting rows are not the address lookups

Lexical search is strong when the query names `100 Harbor Example Road`. The rows that justify hybrid + a wide pool are **jargon and multi-doc** questions (hail / storm-created opening / plumbing-not-storm). Address singles are still gated: they catch routing and gate regressions.

Honest limits of the harness: **15 synthetic reports**, short documents, small gold set. Catches retrieval regressions. Not absolute quality on the real Drive corpus.

---

## 3. How the pipeline and the two cutoffs fit

```
Query
  → normalize_retrieval_query
  → first-pass retrieve (vector / lexical / hybrid+RRF) at pool_k = P
       → recall@pool on unique doc_ids
  → optional cross-encoder rerank
  → slice to top_k
       → recall@k / hit@k / MRR
  → cosine relevance gate
  → generate
       → (separate suite) NliJudge faithfulness
```

Code: [`tests/eval/retrieval_runner.py`](../tests/eval/retrieval_runner.py), [`tests/eval/test_retrieval.py`](../tests/eval/test_retrieval.py), [`tests/eval/retrieval_metrics.py`](../tests/eval/retrieval_metrics.py). Production hook: `candidate_k` + `RetrieveOutcome.pool_chunks` in [`app/main.py`](../app/main.py). Metric math is also covered by normal pytest in [`tests/test_retrieval_metrics.py`](../tests/test_retrieval_metrics.py) (no Docker).

---

## 4. Interview Q → A

| Question | Answer |
| --- | --- |
| What is recall@k? | Of the gold-relevant items, the fraction that appear in the top-k results. |
| What is recall@pool? | Same fraction, but in the **first-pass candidate pool** of size \(P\) before rerank/trim. |
| Why does first-pass recall matter more than post-rerank recall? | The reranker can only reorder what first-pass found. If the right report never entered the pool, reranking cannot save it. |
| How would you know the reranker is the bottleneck? | High recall@pool, low recall@k. Widen \(P\) or fix first-pass if pool recall is low; look at the cross-encoder / trim if pool is high and @k is low. |
| Why not measure recall@pool in production metrics? | It needs gold labels. Live traffic has none. Watch pool *size*, gate-pass, and cosine instead. |
| Why document IDs instead of chunk IDs? | Chunk IDs break when you rechunk. Forensic failures are usually the wrong property. |
| Why not LLM-as-judge for retrieval? | We have a labeled frozen corpus. LLM judges add cost and noise; we already use NLI for generation faithfulness. |
| What is nDCG@k? | Ranking quality: relevant items count more higher up, normalized to the ideal ranking. Needs graded labels to shine; we have binary gold today. |
| What is MRR? | Mean of \(1/\)rank of the **first** relevant result. |
| When is MRR the wrong summary? | When several reports are jointly relevant — it ignores everything after the first hit. |
| Why gate on cosine, not RRF? | RRF encodes rank fusion, not absolute relevance. A top RRF score can still be off-corpus. |
| Why gate on cosine, not ts_rank? | `ts_rank` shifts as the corpus grows (IDF). Cosine is pairwise between two vectors. |
| Why monitor rerank candidate count? | Too small caps recall@pool; too large grows rerank latency roughly linearly. |
| Why track index size next to recall? | Recall@k is only comparable against a frozen corpus. Chunking or corpus growth moves the number without “retrieval getting smarter.” |
| First infra check when live retrieval drops suddenly? | Embedding **model version**. Different versions are different vector spaces; re-embed the corpus. |
| Why hybrid (RRF) instead of vector-only? | Embeddings smear domain jargon (`hail`, claim IDs). Lexical hits those tokens; RRF fuses both lists. Ablation table on the gold set is how we show it. |
| Why keep `must_mention` if you have doc labels? | Labels catch the wrong report. Term checks catch the right report with the key phrase missing from the prompt context. |
| What does hit@k give you that recall@k does not? | A binary “was *anything* useful in the prompt?” For multi-relevant questions with \(k < |gold|\), recall@k cannot be 1.0 even when retrieval is doing its job. |

---

## Quick reference (this suite)

| Thing | Where |
| --- | --- |
| Gold labels | `relevant_doc_ids` in `tests/eval/gold_questions.yaml` |
| Lab sheet | [test-plan.md](test-plan.md) — what / when / how / fill-in results |
| Fast gate | `make eval` → `eval_fast` (retrieval + NLI faithfulness) |
| Retrieval only | `VERBIAGE_EVAL=1 pytest -m eval_fast tests/eval/test_retrieval.py -s` (Docker + embedding cache; **no LLM**) |
| Rerank comparison | `make eval-retrieval-rerank` |
| Metric unit tests | `pytest tests/test_retrieval_metrics.py` (no Docker) |
