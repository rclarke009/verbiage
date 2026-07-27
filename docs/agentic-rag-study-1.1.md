# 1.1 Learn the pattern — Agentic RAG vs static retrieval

**Goal (one session):** Explain plainly what makes retrieval *agentic* vs *static*.  
**Done when:** You can say it in three sentences without jargon soup.

---

## The three sentences (write yours, then check)
Agentic rag allows the system to loop if retrieval fails or the generated answer doesn't pass a faithfulness eval.  The system is agentic meaning that the AI decides based on the decide → act → reassess → stop loop.  what to try next and chooses the tools to try it.  The agency is over that loop, not smarter embeddings.




Draft your own first, then compare:

> **Static retrieval** embeds the question once, pulls top-k chunks once, and generates — no second look.  
> **Agentic retrieval** treats retrieval as a *decision loop*: assess whether context is enough, then rewrite the query, try another tool, or stop and refuse.  
> **The difference is agency over the loop** — not “smarter embeddings,” but *decide → act → reassess → stop*.

If your version says roughly that, you’re done with 1.1.

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

Your `auto` router is **one-shot strategy selection**.  
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

## Map to Verbiage’s next steps (preview only)

| Later step | Agentic idea it implements |
|------------|----------------------------|
| **1.3** Reformulate on gate fail | Corrective rewrite, one retry |
| **1.4** Multi-tool via MCP | Agent-as-retriever (hybrid / nearby_storm / metadata) |
| **1.5** Sufficiency judge + stop | Core loop: decide → act → reassess → stop |

1.1 is only the mental model. Don’t build yet.

---

## Sources (read selectively — ~45–90 min)

**Must-skim (concepts):**

1. [Self-Reflective RAG with LangGraph](https://www.langchain.com/blog/agentic-rag-with-langgraph) — CRAG + Self-RAG as graphs with grade/rewrite loops  
2. [Adaptive-RAG paper](https://arxiv.org/abs/2403.14403) (Jeong et al.) — route by query complexity  
3. [CRAG paper](https://arxiv.org/abs/2401.15884) — evaluate retrieval, then correct  

**Optional depth:**

4. [Agentic RAG survey](https://arxiv.org/html/2501.09136) — taxonomy (reflection, planning, tool use)  
5. LangGraph adaptive/corrective cookbook notebooks (search: “LangGraph Adaptive RAG”) — concrete node graphs  

**How to read:** For each source, extract only: *What decision is made? After which step? What happens on failure? What is the stop condition?*

---

## Self-check (pass / fail)

Answer out loud or on paper:

1. Why is Verbiage’s cosine gate **not** the same as a full agentic loop?
it doesn't loop back to try again - it passes or fails in one pass.  
2. Name one failure mode static RAG has that a rewrite-once loop can fix. a false refuse — the answer is in the corpus, but the original wording missed it; one rewrite can recover.  if the retrieval doesn't include related context but that context exists, the system can try once more to find it? 
3. Name one failure mode a rewrite loop can **create** if you ignore unanswerable questions.  
hallucinated incorrect answers? an unanswerable / off-corpus query gets rewritten into something that matches something, so the system answers instead of refusing. That’s the product risk for Verbiage.
4. In one sentence: difference between Verbiage `auto` and Adaptive RAG (paper).
adaptive rag routes queries based on their content, verbiage auto always routes to same retrieval methods and verification path. (not quite)

**Expected gist:**

1. Gate is a one-shot yes/no before generate; it doesn’t rewrite or try another tool.  
2. Good answer exists, but the original wording missed the right chunks (false refuse).  
3. Off-corpus query gets rewritten into something that matches *something* → false answer / hallucination.  
4. `auto` picks lexical vs hybrid once by query shape; Adaptive RAG chooses whether/how many retrieval steps by complexity (and may loop).

---

## Session checklist

- [ ] Read LangGraph agentic RAG blog (or CRAG section)  
- [ ] Skim Adaptive-RAG abstract + figure for routing levels  
- [ ] Write your own 3 sentences (section above)  
- [ ] Pass the four self-check questions  
- [ ] Note one Verbiage gold question that might benefit from rewrite-once (guess is fine) water_damage_storm_opening

When those are checked, **1.1 is done.** Next is **1.2** — retrieval metrics baseline on the current single-pass system.
