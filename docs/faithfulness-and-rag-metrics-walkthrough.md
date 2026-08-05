# Faithfulness & RAG metrics — plain-language walkthrough

This is a beginner guide to the Q&A set about **NliJudge**, **faithfulness**, **refusal gates**, and **RAG drift metrics** in Verbiage. Read it top to bottom once; later use the flashcard answers at the end of each section as a quiz.

---

## 0. The story in one paragraph

Verbiage answers questions from a corpus of reports (RAG = retrieve chunks → generate an answer). Two silent failure modes matter:

1. **Hallucination** — the model invents facts not in the retrieved text.
2. **Quality drift** — retrieval or gating slowly (or suddenly) gets worse, but nothing crashes.

The harness below catches (1) on a small frozen gold set, and the live metrics catch (2) over time. One number is never enough; you need a small set of metrics that each blame a different layer.

---

## 1. Faithfulness: “Did the answer stick to the sources?”

### What “faithfulness” means here

Break the model’s answer into **claims** (roughly sentences). For each claim, ask: *is this claim supported by the context we actually retrieved?*

**Faithfulness score** = supported claims ÷ total claims (scale 0–1).

- `1.0` = every claim is grounded.
- `0.5` = half the claims are unsupported (bad).
- Refusals (“I don’t have relevant context…”) have no claims to check → treated as fine for this score.

### The fast gold-set gate wants 1.0

On the hand-built gold questions, the fast eval (`make eval` / NliJudge) requires **faithfulness = 1.0** — every claim supported. That’s a **regression gate**, not a claim that production is perfect forever.

### Claim-level fail detail

Overall faithfulness only says *how many* claims failed. **Per-claim fail detail** lists *which* claims failed. That matters for debugging: if failures cluster in one claim type (addresses, dates, cause-of-loss wording), dig into **chunking, premise construction, or prompt style** before blaming the LLM.

### Honest limit of the whole harness

The gold set is **small and hand-built**. It catches regressions when you tweak retrieval/prompts. It does **not** measure absolute real-world quality.

---

## 2. NliJudge: how we decide “supported” without calling OpenAI every tweak

**NLI** = Natural Language Inference. A small local model scores: given a **premise** (source text) and a **hypothesis** (one claim from the answer), how strongly does the premise **entail** the claim?

### Per-claim NLI entailment probability

A number from **0 to 1**: how strongly *this* premise entails *this* claim.

- Near `1` → “yes, the source says that.”
- Near `0` → “no support / contradiction / unrelated.”

### When does a claim count as supported?

Take the **best** (highest) entailment probability across candidate premises. If that best score is **≥ 0.5**, the claim is supported.

### Which premise forms get scored?

For each retrieved chunk/block, NliJudge builds **three forms** and scores them all:

1. **Whole chunk** — helps claims that need several sentences together.
2. **Single sentence** — helps when a long multi-topic chunk dilutes a single fact.
3. **Header + sentence** — stitches the section title onto a body sentence.

Then it takes the **max** over all of those (max-pool), not the average.

### Why max-pool, not average?

**One strong premise is enough.** Averaging would drown a perfect match in a pile of irrelevant premises and make supported claims look unsupported.

### What does header+sentence fix?

**Coreference.** Example: the header says `412 Example Drive`, the body says `this residence had wind damage`. The claim names the address. Neither bare sentence nor a truncated full block may entail that claim alone; **header + sentence** bridges the gap.

---

## 3. Refusal metrics: “Did we refuse when we should — and only then?”

Before the LLM runs, a **relevance gate** can refuse off-corpus questions (cosine similarity too low). Gold questions include both answerable and deliberately unanswerable ones.

| Metric | Plain meaning | What you want |
| --- | --- | --- |
| **Refusal rate** (on should-refuse / unanswerable gold) | Fraction of off-corpus gold questions correctly refused | **1.0** (or at/near it) |
| **False-refusal rate** | Grounded (answerable) gold questions that started refusing | **~0** |

### If refusal rate on should-refuse drops

The gate **loosened**, or off-corpus answers are getting through (hallucination risk + wasted spend).

### If false-refusal rate on grounded gold rises

The gate **tightened**, or the retrieval signal used for gating changed — good questions now get “I don’t have context.”

### Real regression this caught

**Gating on RRF score instead of cosine similarity.** Unit tests still passed. False-refusal (and the calibration story below) is what surfaced it.

---

## 4. Why RAG quality drift is hard — and what makes a metric usable

### Why isn’t one metric enough?

A single score can’t tell **retrieval failure** apart from **generation failure**. You need complementary signals (gate, cosine, recall, faithfulness, latency, …).

### Why is drift silent?

Bad output often **looks like** good output. Nothing throws an exception. Users may not notice until trust erodes.

### What makes a metric usable for drift detection?

It must be **comparable over time against a frozen baseline** (same gold set, same corpus snapshot, same embedding model version, etc.). If the baseline moves under you, the number is noise.

---

## 5. Live gate & cosine: watching production without waiting for gold eval

### Gate-pass rate

Fraction of **live** queries that clear the relevance gate and reach generation.

If this shifts with **no code change**, the **corpus or query mix** changed (more off-topic traffic, new docs, seasonal question patterns, …).

### Which retrieval signal at the gate?

**Max cosine similarity per query** — best chunk vs query. That’s the absolute “how related is the best hit?” signal.

### Calibration numbers (eval corpus)

| Situation | Typical best cosine |
| --- | --- |
| Off-corpus | ~**0.42** |
| Grounded gold | ≥ **0.56** |
| **Gate threshold** | **0.5** |

So 0.5 sits in the gap: refuses clear off-corpus, clears grounded gold.

### If that gap narrows

Off-corpus and grounded scores start overlapping → the cosine threshold **no longer discriminates cleanly**. Retune carefully; don’t just lower the gate blindly.

### Why gate on cosine, not RRF?

**RRF encodes rank, not absolute relevance.** Being “#1 of a bad list” can still be irrelevant.

### Why gate on cosine, not `ts_rank`?

**`ts_rank` shifts as the corpus grows** (IDF / term rarity depends on corpus-wide frequencies). Cosine is **pairwise between two vectors**, so corpus growth doesn’t move it the same way.

---

## 6. Retrieval-quality metrics (offline / gold retrieval)

These answer: “Did we find the right chunks?” — separate from “Did the LLM phrase them faithfully?”

### Lexical-arm hit-rate collapse

Sudden collapse of lexical (full-text) hits → **query mix changed**, or **`tsvector` / stemming broke**.

### First infrastructure check when live retrieval quality drops suddenly

**Embedding model version.** Different versions embed into **different spaces**. Old vectors + new query embeddings = nonsense similarity. After a version change: **re-embed the whole corpus**.

### recall@k

Of the gold-relevant chunks, what fraction appear in the **top-k** results?

In a **retrieve-then-rerank** pipeline, **first-pass recall@k matters most**: the reranker can only reorder what first-pass found. If the right chunk never entered the candidate pool, reranking can’t save it.

### nDCG@k

**Ranking quality**: relevant items count more when ranked higher; normalized to the ideal ranking. Especially useful for judging **ranked lists** — including **reranker** quality.

### MRR (Mean Reciprocal Rank)

Average of **1 / (rank of first relevant result)**. Great when you mainly care that *some* good hit is near the top.

**Wrong when several chunks are jointly relevant** — MRR ignores everything after the first hit.

### Track index size / chunk count with recall@k

**recall@k is only comparable against a frozen corpus.** If chunking or corpus size changes, recall can move for reasons unrelated to “retrieval got smarter.”

---

## 7. Latency & rerank ops

### Catching a reranker regression

Watch **p95 latency at the rerank stage** (not only end-to-end).

End-to-end can **hide** a stage regression: cheap/fast requests average the pain away; p95 on the stage still shows it.

### Monitor rerank candidate count

- **Too small** → caps recall (good chunks never enter the pool).
- **Too large** → latency grows roughly **linearly** with candidates.

---

## 8. Citation coverage (concept only — not a current suite metric)

**Citation coverage** = fraction of generated sentences with a **traceable source**. Useful product idea; not what the current faithfulness suite scores. Faithfulness asks “is the claim entailed by context?”; citation coverage asks “did we attach a pointer?”

---

## Flashcard cheat sheet (same Q → A as your list)

| Question | Answer |
| --- | --- |
| Per-claim NLI entailment probability? | How strongly a premise entails one claim. Scale 0–1. |
| When does a claim count as supported? | Best NLI entailment over candidate premises ≥ 0.5. |
| Which premise forms before best entailment? | Whole chunk, single sentence, header+sentence. |
| Max-pool or average? | Max. One strong premise is enough. |
| Why max-pool not average? | Averaging drowns a perfect match in irrelevant premises. |
| What does header+sentence fix? | Coreference — address in header, fact in body. |
| How is faithfulness scored? | Supported claims ÷ total claims. Scale 0–1. |
| Fast gold-set faithfulness gate requires? | 1.0 (all claims supported). |
| Claim-level fail detail adds? | Which claims fail, not just how many. |
| Unsupported claims cluster in one type? | Often chunking / premise construction / prompt style — dig before blaming the LLM. |
| Refusal rate on should-refuse gold? | Fraction of off-corpus gold questions correctly refused. |
| Expected refusal rate there? | 1.0 (or at/near it). |
| Refusal rate drops means? | Gate loosened, or off-corpus answers getting through. |
| False-refusal rate? | Grounded gold questions that started refusing. |
| False-refusal rises means? | Gate tightened, or gating signal changed. |
| Regression false-refusal caught? | Gating on RRF instead of cosine. Unit tests still passed. |
| Honest limit of faithfulness harness? | Small hand-built gold set. Catches regressions; not absolute quality. |
| Why isn’t one metric enough for drift? | Can’t separate retrieval failure from generation failure. |
| Why is RAG quality drift silent? | Bad output looks like good output. Nothing throws. |
| What makes a metric usable for drift? | Comparable over time against a frozen baseline. |
| Gate-pass rate? | Fraction of live queries that clear the relevance gate and reach generation. |
| Gate-pass shifts with no code change? | Corpus or query mix changed. |
| Retrieval signal watched at gate? | Max cosine similarity per query (best chunk vs query). |
| Cosine calibration numbers? | Off-corpus ~0.42 vs grounded ≥ 0.56. Gate threshold 0.5. |
| Cosine gap narrows means? | Threshold no longer discriminates cleanly. |
| Why gate on cosine not RRF? | RRF encodes rank, not absolute relevance. |
| Why gate on cosine not ts_rank? | ts_rank shifts as the corpus grows. |
| Why corpus growth moves ts_rank? | IDF depends on corpus-wide term frequency. |
| Why cosine doesn’t move the same way? | Cosine is pairwise between two vectors. |
| Lexical-arm hit-rate collapse means? | Query mix changed, or tsvector/stemming broke. |
| First infra check when retrieval drops? | Embedding model version. |
| Why embedding version change breaks retrieval? | Different versions embed into different spaces. |
| After embedding version change? | Re-embed the whole corpus. |
| recall@k? | Of gold-relevant chunks, fraction in top-k. |
| Why first-pass recall@k matters most? | Reranker can only reorder what first-pass found. |
| nDCG@k? | Ranking quality: relevant items count more higher up (normalized to ideal). |
| nDCG@k especially useful for? | Ranked lists — including reranker quality. |
| MRR? | Average of 1 / (rank of first relevant result). |
| When is MRR wrong? | When several chunks are jointly relevant. |
| Why track index size / chunk count with recall@k? | recall@k only comparable against a frozen corpus. |
| Latency for reranker regression? | p95 at the rerank stage. |
| Why end-to-end can hide it? | Cheap requests average a stage regression away. |
| Why monitor rerank candidate count? | Too small caps recall; too large grows latency linearly. |
| Citation coverage (concept only)? | Fraction of generated sentences with a traceable source. |

---

## Mental model (layers)

```
Query
  → retrieve (vector / lexical / hybrid+RRF)
  → optional rerank
  → relevance gate (max cosine ≥ 0.5?) ──no──► refuse
  → generate answer + citations
  → (eval) split claims → NliJudge vs retrieved context → faithfulness
```

**Live drift:** gate-pass, cosine, lexical hit-rate, stage latency, embedding version, index size.

**Gold regression:** faithfulness 1.0, refusal 1.0 on should-refuse, false-refusal ~0, plus claim-level fails.

Code pointers: [`tests/eval/judges.py`](../tests/eval/judges.py) (NliJudge), [`tests/eval/test_faithfulness.py`](../tests/eval/test_faithfulness.py), [`app/config.py`](../app/config.py) (`RAG_MIN_RELEVANCE_SCORE`), [`setup_and_testing.md`](../setup_and_testing.md) (how to run `make eval`).
