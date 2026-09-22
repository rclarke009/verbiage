"""Labeled retrieval eval: recall@pool, recall@k, MRR on the frozen demo corpus.

LLM-free. Shares the eval DB fixture with the faithfulness suite.

    make eval                  # includes this module via eval_fast
    pytest -m eval_fast tests/eval/test_retrieval.py -s   # retrieval only
    make eval-retrieval-rerank # optional MiniLM rerank comparison
"""

from __future__ import annotations

import pytest

from embedding_cache import CachedEmbedder
from retrieval_metrics import recall_at
from retrieval_runner import (
    ABLATION_MODES,
    POOL_K,
    RetrievalResult,
    answerable_questions,
    rag_answerable_questions,
    run_retrieval_sync,
)
from runner import load_gold_questions

GOLD = load_gold_questions()
ANSWERABLE = answerable_questions()
ANSWERABLE_IDS = [q["id"] for q in ANSWERABLE]
RAG_ANSWERABLE = rag_answerable_questions()

_SCORE_ROWS: list[RetrievalResult] = []
_ABLATION: dict[str, list[RetrievalResult]] = {}


@pytest.fixture(scope="session")
def retrieval_embedder():
    return CachedEmbedder()


@pytest.fixture(scope="session")
def auto_results(eval_conn, retrieval_embedder):
    """One auto-path retrieve per answerable gold question."""
    return {
        q["id"]: run_retrieval_sync(eval_conn, q, embedder=retrieval_embedder)
        for q in ANSWERABLE
    }


@pytest.fixture(scope="session", autouse=True)
def _scoreboard(auto_results):
    yield
    if not auto_results:
        return
    sample = next(iter(auto_results.values()))
    print("\n\nMYDEBUG -> retrieval scoreboard")
    print(f"corpus n_docs={sample.n_docs} n_chunks={sample.n_chunks} pool_k={POOL_K}")
    print(
        f"{'question_id':32} {'cat':18} {'r@pool':6} {'r@k':6} {'hit@k':5} {'mrr':5} "
        f"{'mode':8} pool_docs"
    )
    for qid in ANSWERABLE_IDS:
        res = auto_results[qid]
        _SCORE_ROWS.append(res)
        rpool = "n/a" if res.recall_pool is None else f"{res.recall_pool:.2f}"
        rk = "n/a" if res.recall_k is None else f"{res.recall_k:.2f}"
        hit = "n/a" if res.hit_k is None else f"{res.hit_k:.0f}"
        mrr_s = "n/a" if res.mrr is None else f"{res.mrr:.2f}"
        print(
            f"{res.question_id:32} {res.category:18} {rpool:6} {rk:6} {hit:5} {mrr_s:5} "
            f"{res.resolved_mode:8} {','.join(res.pool_doc_ids[:6])}"
        )
    if _ABLATION:
        print("\nMYDEBUG -> retrieval mode ablation (mean over RAG answerable)")
        print(f"{'mode':10} {'n':3} {'mean r@pool':12} {'mean r@k':10} {'mean MRR':8}")
        for mode in ABLATION_MODES:
            rows = _ABLATION.get(mode) or []
            if not rows:
                continue
            pools = [r.recall_pool for r in rows if r.recall_pool is not None]
            ks = [r.recall_k for r in rows if r.recall_k is not None]
            mrrs = [r.mrr for r in rows if r.mrr is not None]
            mean_p = sum(pools) / len(pools) if pools else float("nan")
            mean_k = sum(ks) / len(ks) if ks else float("nan")
            mean_m = sum(mrrs) / len(mrrs) if mrrs else float("nan")
            print(f"{mode:10} {len(rows):3} {mean_p:12.3f} {mean_k:10.3f} {mean_m:8.3f}")


@pytest.mark.eval_fast
@pytest.mark.parametrize("q", ANSWERABLE, ids=ANSWERABLE_IDS)
def test_recall_at_pool_auto(q, auto_results):
    res = auto_results[q["id"]]
    assert res.recall_pool is not None, f"{q['id']}: missing relevant_doc_ids"
    assert not res.gate_blocked, (
        f"{q['id']}: cosine gate dropped a grounded question before the pool could be scored"
    )
    assert res.recall_pool == 1.0, (
        f"{q['id']}: recall@pool={res.recall_pool:.2f} (gold {res.relevant_doc_ids} "
        f"not all in pool {res.pool_doc_ids})"
    )


@pytest.mark.eval_fast
@pytest.mark.parametrize("q", ANSWERABLE, ids=ANSWERABLE_IDS)
def test_recall_at_k_auto(q, auto_results):
    res = auto_results[q["id"]]
    assert res.recall_k is not None
    assert res.hit_k is not None
    if q["category"] == "answerable_single":
        assert res.recall_k == 1.0, (
            f"{q['id']}: recall@k={res.recall_k:.2f} gold={res.relevant_doc_ids} "
            f"prompt={res.prompt_doc_ids}"
        )
    else:
        assert res.hit_k == 1.0, (
            f"{q['id']}: hit@k=0 gold={res.relevant_doc_ids} prompt={res.prompt_doc_ids} "
            f"(recall@k={res.recall_k:.2f})"
        )


@pytest.mark.eval_fast
def test_mode_ablation_scoreboard(eval_conn, retrieval_embedder, auto_results):
    """Informational: vector / lexical / hybrid / auto means. Not a second gate."""
    for mode in ABLATION_MODES:
        rows: list[RetrievalResult] = []
        for q in RAG_ANSWERABLE:
            if mode == "auto":
                rows.append(auto_results[q["id"]])
            else:
                rows.append(
                    run_retrieval_sync(
                        eval_conn, q, retrieval_mode=mode, embedder=retrieval_embedder
                    )
                )
        _ABLATION[mode] = rows
    assert _ABLATION["auto"], "ablation produced no auto rows"


@pytest.mark.eval_retrieval_rerank
def test_rerank_vs_slice_recall_k(eval_conn, retrieval_embedder, auto_results):
    """Same first-pass pool; MiniLM reorder vs slice-to-top_k. Not in make eval."""
    from app.reranker import Reranker

    reranker = Reranker()
    print("\n\nMYDEBUG -> rerank vs slice recall@k")
    print(f"{'question_id':32} {'r@pool':6} {'slice@k':7} {'rerank@k':8}")
    for q in RAG_ANSWERABLE:
        sliced = auto_results[q["id"]]
        reranked = run_retrieval_sync(
            eval_conn, q, embedder=retrieval_embedder, reranker=reranker
        )
        pool_match = recall_at(reranked.pool_doc_ids, sliced.relevant_doc_ids)
        print(
            f"{q['id']:32} {sliced.recall_pool:6.2f} {sliced.recall_k:7.2f} "
            f"{reranked.recall_k:8.2f}"
        )
        assert pool_match == sliced.recall_pool, (
            f"{q['id']}: rerank changed first-pass pool recall "
            f"({pool_match} vs {sliced.recall_pool})"
        )
