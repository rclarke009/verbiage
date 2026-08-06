# Agentic RAG vs static retrieval

Design notes on what makes retrieval *agentic* vs *static*, and how that maps to Verbiage today.

## Summary

> **Static retrieval** embeds the question once, pulls top-k chunks once, and generates — no second look.  
> **Agentic retrieval** treats retrieval as a *decision loop*: assess whether context is enough, then rewrite the query, try another tool, or stop and refuse.  
> **The difference is agency over the loop** — not “smarter embeddings,” but *decide → act → reassess → stop*.

---

## Static RAG (what most systems — including Verbiage Ask today — do)

```
query → embed → retrieve top-k → (optional rerank) → LLM → answer
                      ↑
              one pass, fixed plan
```

Characteristics:

- Pipeline shape is fixed at request time
- Failures are terminal (empty / low score → refuse) or silent (weak chunks → hallucinate)
- “Adaptive” here usually means **routing once** (lexical vs hybrid), not looping

**Verbiage today (Ask):**

```
question → resolve_auto_mode → hybrid|lexical|vector
        → relevance gate (cosine)
        → optional cross-encoder rerank
        → LLM with citations  OR  refuse
```

Plus a special non-loop route: `nearby_storm` (structured geo lookup, no LLM).

That is **strong single-pass RAG**. It is not yet agentic.

---

## What “agentic” actually means here

Not “uses an agent framework.” Agentic retrieval means the system can **change its mind after seeing retrieval results**.

| Pattern | What it adds | One-line idea |
|---------|--------------|---------------|
| **Query rewrite / decompose** | Second retrieval with a better question | Gate failed? Rephrase and try once |
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

Verbiage’s `auto` router is **one-shot strategy selection**.  
Agentic Adaptive RAG is **strategy + optional multi-step retrieval based on assessed need**.

---

## Tiny decision tree (plain English)

```
Got chunks that actually answer the question?
  ├─ Yes → answer (cite)
  ├─ Maybe / wrong shape → rewrite query OR switch tool → retrieve again
  └─ Clearly off-corpus → refuse (stop)
```

Stop conditions matter. Without them you get infinite rewrite loops and burn tokens. Verbiage’s product stance (refuse when evidence is weak) is a *feature* — agentic work should preserve that, not bypass it.

---

## Possible Verbiage extensions

| Extension | Agentic idea it implements |
|-----------|----------------------------|
| Reformulate on gate fail | Corrective rewrite, one retry |
| Multi-tool via MCP | Agent-as-retriever (hybrid / nearby_storm / metadata) |
| Sufficiency judge + stop | Core loop: decide → act → reassess → stop |

These are design options relative to the current single-pass Ask path — not a committed roadmap.

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

1. Verbiage’s cosine gate is a **one-shot** yes/no before generate; it does not rewrite or try another tool — so it is not a full agentic loop.
2. A rewrite-once loop can fix a **false refuse** (answer exists in the corpus, original wording missed it).
3. The same loop can **create** risk if an off-corpus query is rewritten into something that matches *something* and the system answers instead of refusing.
4. Verbiage `auto` picks lexical vs hybrid once by query shape; Adaptive RAG (paper) chooses whether/how many retrieval steps by complexity (and may loop).
