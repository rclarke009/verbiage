# Agentic RAG vs static retrieval

Design notes on what makes retrieval *agentic* vs *static*, and how that maps to Verbiage today.

## Summary

> **Static retrieval** embeds the question once, pulls top-k chunks once, and generates — no second look.  
> **Agentic retrieval** treats retrieval as a *decision loop*: assess whether context is enough, then rewrite the query, try another tool, or stop and refuse.  
> **The difference is agency over the loop** — not “smarter embeddings,” but *decide → act → reassess → stop*.

---

## Where Verbiage Ask sits today

Ask is **mostly single-pass**, with one **bounded corrective step** after a soft refuse:

```
question
  → normalize_retrieval_query (strip instructional fluff; keep topic for embed/lexical)
  → resolve_auto_mode → hybrid|lexical|vector
  → relevance gate (cosine)
  → optional cross-encoder rerank
  → LLM with citations
       ├─ normal answer → done
       ├─ hard refuse (gate/empty) → done (no rewrite)
       └─ soft refuse (“No source documents…”)
            → rewrite_query_for_retry (domain phrase map) — if None, keep soft refuse
            → normalize → embed → retrieve → gate → LLM once more (original question in prompt)
```

Plus a special non-loop route: `nearby_storm` (structured geo lookup, no LLM).

**Code:** [`app/main.py`](../app/main.py) (`_run_ask_rag_with_corrective`), [`app/corrective.py`](../app/corrective.py), [`app/retrieval.py`](../app/retrieval.py) (`normalize_retrieval_query`).

That is **not** a full agentic loop (no multi-tool planner, no unbounded retries). It *is* a small decide → act → stop corrective: soft refuse can trigger **exactly one** rewrite-and-retrieve when the phrase map matches (e.g. intact roof tiles / no storm-created opening).

---

## What “agentic” actually means here

Not “uses an agent framework.” Agentic retrieval means the system can **change its mind after seeing retrieval results**.

| Pattern | What it adds | One-line idea |
|---------|--------------|---------------|
| **Query rewrite / decompose** | Second retrieval with a better question | Soft refuse? Rephrase and try once |
| **Corrective RAG (CRAG)** | Grade docs; if bad → rewrite / fallback | Retrieval is evaluated, not trusted |
| **Self-RAG** | Reflect on answer + evidence | Generate, then check support / retry |
| **Adaptive RAG** (paper sense) | Route by *complexity*: no retrieval / single-shot / multi-hop | Don’t always pay for the full stack |
| **Agent-as-retriever / multi-tool** | Choose among tools (vector, lexical, SQL, MCP…) | Retriever is a toolbox, not one call |

**Stacking (common in LangGraph cookbooks):**

1. **Route** (Adaptive) — which strategy?
2. **Retrieve**
3. **Grade / sufficiency** (Corrective) — good enough?
4. If no → **rewrite** and loop (with a stop condition)
5. **Generate** (+ optional faithfulness check)

Interview soundbite: *“Adaptive is which path; corrective is whether to loop; agentic is owning that loop with a stop condition.”*

---

## Don’t confuse these two “adaptive”s

| Name in Verbiage | Name in papers / LangGraph | Same thing? |
|------------------|----------------------------|-------------|
| `retrieval_mode: "auto"` | Adaptive RAG (Jeong et al.) | **No** |
| Rule: short/quoted → lexical, else hybrid | Classifier: no-retrieval / single / iterative | Related idea, much narrower |
| Cosine relevance gate | CRAG document grader | Same *job*, different *signal* (score vs content judge) |
| Soft-refuse rewrite-once | Corrective rewrite | Same *family*; Verbiage triggers after LLM soft refuse, not after a doc grader |

Verbiage’s `auto` router is **one-shot strategy selection**.  
`normalize_retrieval_query` is **topic cleanup** before embed/lexical (prompt still uses the original question) — not a retrieval loop.  
Agentic Adaptive RAG is **strategy + optional multi-step retrieval based on assessed need**.

---

## Tiny decision tree (plain English)

```
Got chunks that actually answer the question?
  ├─ Yes → answer (cite)
  ├─ Gate says no → hard refuse (stop; no rewrite)
  ├─ Soft refuse + rewrite map hits → retrieve once more → answer or keep soft refuse
  └─ Soft refuse + no rewrite map → soft refuse (stop)
```

Stop conditions matter. Without them you get infinite rewrite loops and burn tokens. Verbiage’s product stance (refuse when evidence is weak) is a *feature* — corrective work preserves a hard stop: **at most one** rewrite, and only for a small domain phrase map.

---

## Shipped vs possible next steps

| Status | Capability | Agentic idea |
|--------|------------|--------------|
| **Shipped** | Soft-refuse rewrite-once (`rewrite_query_for_retry`) | Corrective rewrite, one retry |
| **Shipped** | `normalize_retrieval_query` before embed/retrieve | Topic cleanup so fluff does not tank the gate |
| **Possible** | Multi-tool via MCP | Agent-as-retriever (hybrid / nearby_storm / metadata) |
| **Possible** | Sufficiency judge before generate (skip first LLM on weak context) | Decide → act without paying for a soft-refuse LLM call |
| **Possible** | Broader rewrite map / LLM rewrite | Same loop, less hand-tuned phrases |

---

## Sources

**Core concepts:**

1. [Self-Reflective RAG with LangGraph](https://www.langchain.com/blog/agentic-rag-with-langgraph) — CRAG + Self-RAG as graphs with grade/rewrite loops  
2. [Adaptive-RAG paper](https://arxiv.org/abs/2403.14403) (Jeong et al.) — route by query complexity  
3. [CRAG paper](https://arxiv.org/abs/2401.15884) — evaluate retrieval, then correct  

**Optional depth:**

4. [Agentic RAG survey](https://arxiv.org/html/2501.09136) — taxonomy (reflection, planning, tool use)  
5. LangGraph adaptive/corrective cookbook notebooks (search: “LangGraph Adaptive RAG”) — concrete node graphs  

For each source, the useful extract is: *What decision is made? After which step? What happens on failure? What is the stop condition?*

---

## Distinctions worth keeping clear

1. Verbiage’s cosine gate is a **one-shot** yes/no before generate; hard gate fails do **not** rewrite.
2. Rewrite-once runs only after an LLM **soft refuse**, and only when `rewrite_query_for_retry` returns a phrase — it can recover some false soft refuses (answer in corpus, original wording missed it).
3. The same loop can **create** risk if an off-corpus query is rewritten into something that matches *something* and the system answers instead of refusing — hence the narrow phrase map and single retry.
4. Verbiage `auto` picks lexical vs hybrid once by query shape; Adaptive RAG (paper) chooses whether/how many retrieval steps by complexity (and may loop).
