"""Reranker coverage: the Reranker class, the _rerank_chunks adapter, and the
reranking behaviour of _retrieve_for_ask.

All tests stub the cross-encoder so no ~100MB model is loaded. The reranking path
was previously untested; these lock down the invariants that matter:
  - lazy model load happens exactly once,
  - the RetrievedChunk<->dict adapter round-trips,
  - _retrieve_for_ask widens the candidate pool only when a reranker is present,
  - the cosine relevance gate runs BEFORE reranking (a weak retrieval still refuses
    and the reranker is never invoked),
  - lexical results (no cosine, never gated) are still reranked.
"""

import asyncio
import sys
import types

import app.main as main
from app.config import RAG_MIN_RELEVANCE_SCORE
from app.models import AskRequest, RetrievedChunk
from app.reranker import Reranker


def _rc(chunk_id: str, score: float, content: str | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        doc_id="d",
        score=score,
        content_snippet=content if content is not None else f"content-{chunk_id}",
    )


class _FakeModel:
    """Stand-in CrossEncoder: relevance score == len(document), so order is assertable."""

    def __init__(self) -> None:
        self.calls = 0

    def predict(self, pairs):
        self.calls += 1
        return [float(len(doc)) for _query, doc in pairs]


# --- Reranker class --------------------------------------------------------


def test_rerank_sorts_by_score_desc_and_trims():
    r = Reranker()
    r._model = _FakeModel()  # bypass the lazy load
    cands = [{"content": "a"}, {"content": "aaa"}, {"content": "aa"}]
    out = r.rerank("q", cands, top_k=2)
    # score == len(content): "aaa"(3) > "aa"(2) > "a"(1); top_k=2 keeps the first two.
    assert [c["content"] for c in out] == ["aaa", "aa"]
    assert all("rerank_score" in c for c in out)


def test_rerank_empty_returns_empty():
    r = Reranker()
    r._model = _FakeModel()
    assert r.rerank("q", [], top_k=5) == []


def test_get_model_loads_once(monkeypatch):
    """Double-checked locking: repeated _get_model() constructs the model exactly once."""
    constructed = {"n": 0}

    class _FakeCE:
        def __init__(self, name):
            constructed["n"] += 1

        def predict(self, pairs):
            return [0.0 for _ in pairs]

    fake_mod = types.ModuleType("sentence_transformers")
    fake_mod.CrossEncoder = _FakeCE
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_mod)

    r = Reranker()
    m1 = r._get_model()
    m2 = r._get_model()
    assert m1 is m2
    assert constructed["n"] == 1


# --- _rerank_chunks adapter ------------------------------------------------


class _FakeReranker:
    """Reverses candidate order and trims to top_k; records invocations + payload."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_payload = None

    def rerank(self, query, candidates, top_k):
        self.calls += 1
        self.last_payload = candidates
        return list(reversed(candidates))[:top_k]


def test_rerank_chunks_none_is_passthrough():
    chunks = [_rc("a", 0.9), _rc("b", 0.8), _rc("c", 0.7)]
    out = asyncio.run(main._rerank_chunks("q", chunks, top_k=2, reranker=None))
    assert [c.chunk_id for c in out] == ["a", "b"]  # just sliced, order preserved


def test_rerank_chunks_empty_returns_empty():
    out = asyncio.run(main._rerank_chunks("q", [], top_k=5, reranker=_FakeReranker()))
    assert out == []


def test_rerank_chunks_single_candidate_skips_model():
    fake = _FakeReranker()
    out = asyncio.run(main._rerank_chunks("q", [_rc("a", 0.9)], top_k=5, reranker=fake))
    assert [c.chunk_id for c in out] == ["a"]
    assert fake.calls == 0  # len<=1 short-circuits; no model call


def test_rerank_chunks_reorders_and_adapts():
    fake = _FakeReranker()
    chunks = [_rc("a", 0.9), _rc("b", 0.8), _rc("c", 0.7)]
    out = asyncio.run(main._rerank_chunks("q", chunks, top_k=2, reranker=fake))
    # reversed -> [c, b, a], trimmed to 2 -> [c, b]
    assert [c.chunk_id for c in out] == ["c", "b"]
    assert fake.calls == 1
    # adapter handed dicts keyed on "content" (== content_snippet) ...
    assert fake.last_payload[0]["content"] == "content-a"
    # ... and round-trips back to the original RetrievedChunk objects.
    assert all(isinstance(c, RetrievedChunk) for c in out)


# --- _retrieve_for_ask reranking integration -------------------------------


def _spy(calls: dict, key: str, result):
    def _fn(*args, **kwargs):
        calls[key] = args  # capture positional args (incl. pool_k)
        return result

    return _fn


def test_retrieve_for_ask_no_reranker_uses_topk_pool(monkeypatch):
    calls: dict = {}
    monkeypatch.setattr(main, "retrieve_top_k", _spy(calls, "vector", [_rc("v", 0.9)]))
    monkeypatch.setattr(main, "record_retrieval_scores", lambda *a, **k: None)

    req = AskRequest(question="q", retrieval_mode="vector", top_k=5)
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert calls["vector"][2] == 5  # 3rd positional arg is the pool size -> no widening
    assert [c.chunk_id for c in out] == ["v"]


def test_retrieve_for_ask_widens_pool_and_reranks_vector(monkeypatch):
    calls: dict = {}
    pool_chunks = [_rc(str(i), 0.9) for i in range(20)]
    monkeypatch.setattr(main, "retrieve_top_k", _spy(calls, "vector", pool_chunks))
    monkeypatch.setattr(main, "record_retrieval_scores", lambda *a, **k: None)

    fake = _FakeReranker()
    req = AskRequest(question="q", retrieval_mode="vector", top_k=5)
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", fake))

    assert calls["vector"][2] == 20  # max(top_k*4, 20) == 20
    assert fake.calls == 1
    assert len(out) == 5  # reranked pool trimmed back to top_k


def test_retrieve_for_ask_gate_blocks_before_rerank(monkeypatch):
    """A retrieval below the cosine gate refuses (-> []) and never reaches the reranker."""
    below = RAG_MIN_RELEVANCE_SCORE - 0.1
    monkeypatch.setattr(main, "retrieve_top_k", lambda *a, **k: [_rc("weak", below)])
    monkeypatch.setattr(main, "record_retrieval_scores", lambda *a, **k: None)

    fake = _FakeReranker()
    req = AskRequest(question="q", retrieval_mode="vector", top_k=5)
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", fake))

    assert out == []
    assert fake.calls == 0


def test_retrieve_for_ask_lexical_is_reranked(monkeypatch):
    calls: dict = {}
    lex = [_rc("l1", 0.05), _rc("l2", 0.04), _rc("l3", 0.03)]
    monkeypatch.setattr(main, "retrieve_top_k_lexical", _spy(calls, "lexical", lex))
    monkeypatch.setattr(main, "record_lexical_scores", lambda *a, **k: None)

    fake = _FakeReranker()
    req = AskRequest(question="some exact phrase", retrieval_mode="lexical", top_k=2)
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", fake))

    assert calls["lexical"][2] == 20  # lexical pool widened too (no cosine, never gated)
    assert fake.calls == 1
    # reversed [l3, l2, l1] trimmed to 2 -> [l3, l2]
    assert [c.chunk_id for c in out] == ["l3", "l2"]
