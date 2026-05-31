"""Hybrid retrieval: RRF fusion (pure) and /ask mode routing (monkeypatched, no DB)."""

import app.main as main
from app.models import AskRequest, RetrievedChunk
from app.retrieval import FusedHit, _rrf_fuse, resolve_auto_mode


def _rc(chunk_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(chunk_id=chunk_id, doc_id="d", score=score, content_snippet="c")


# --- Tier 1: _rrf_fuse (pure, deterministic) -------------------------------


def test_rrf_chunk_in_both_lists_outranks_one_sided():
    vec = [_rc("a", 0.9), _rc("b", 0.8)]
    lex = [_rc("b", 0.05), _rc("d", 0.04)]
    fused = _rrf_fuse(vec, lex, top_k=5)
    assert fused[0].chunk.chunk_id == "b"  # present in both lists -> wins


def test_rrf_retains_component_scores_and_nulls_missing():
    vec = [_rc("a", 0.9), _rc("b", 0.8)]
    lex = [_rc("b", 0.05), _rc("d", 0.04)]
    by_id = {h.chunk.chunk_id: h for h in _rrf_fuse(vec, lex, top_k=5)}
    assert by_id["b"].cosine_score == 0.8
    assert by_id["b"].lexical_score == 0.05
    assert by_id["a"].lexical_score is None  # vector-only -> None, NOT 0.0
    assert by_id["d"].cosine_score is None  # lexical-only -> None, NOT 0.0


def test_rrf_score_math_and_score_field_alignment():
    fused = _rrf_fuse([_rc("a", 0.9)], [_rc("a", 0.05)], top_k=1, k=60)
    # "a" is rank 1 in both lists -> 1/61 + 1/61
    assert abs(fused[0].rrf_score - (2 / 61)) < 1e-9
    assert fused[0].chunk.score == fused[0].rrf_score


def test_rrf_records_per_list_ranks():
    fused = _rrf_fuse([_rc("a", 0.9), _rc("b", 0.8)], [_rc("b", 0.05)], top_k=5)
    by_id = {h.chunk.chunk_id: h for h in fused}
    assert by_id["b"].vector_rank == 2
    assert by_id["b"].lexical_rank == 1
    assert by_id["a"].lexical_rank is None


def test_rrf_respects_top_k():
    fused = _rrf_fuse([_rc("a", 1), _rc("b", 1), _rc("c", 1)], [], top_k=2)
    assert len(fused) == 2


def test_rrf_empty_inputs():
    assert _rrf_fuse([], [], top_k=5) == []


def test_rrf_orders_by_descending_score():
    fused = _rrf_fuse([_rc("a", 0.9), _rc("b", 0.8), _rc("c", 0.7)], [_rc("c", 0.05)], top_k=5)
    scores = [h.rrf_score for h in fused]
    assert scores == sorted(scores, reverse=True)


def test_rrf_smaller_k_amplifies_rank_gaps():
    # Lower k -> larger 1/(k+rank), so a top-ranked chunk pulls further ahead.
    high_k = _rrf_fuse([_rc("a", 0.9)], [], top_k=1, k=60)[0].rrf_score
    low_k = _rrf_fuse([_rc("a", 0.9)], [], top_k=1, k=10)[0].rrf_score
    assert low_k > high_k


# --- Tier 3: _retrieve_for_ask mode routing (monkeypatched) ----------------


def test_retrieve_for_ask_vector_mode(monkeypatch):
    calls: dict[str, bool] = {}
    monkeypatch.setattr(main, "retrieve_top_k", lambda *a, **k: (calls.setdefault("vector", True), [_rc("v", 0.9)])[1])
    monkeypatch.setattr(main, "record_retrieval_scores", lambda *a, **k: calls.setdefault("rec_cosine", True))
    monkeypatch.setattr(main, "retrieve_top_k_hybrid", lambda *a, **k: calls.setdefault("hybrid", True))
    monkeypatch.setattr(main, "retrieve_top_k_lexical", lambda *a, **k: calls.setdefault("lexical", True))

    req = AskRequest(question="q", retrieval_mode="vector")
    out = main._retrieve_for_ask(None, req, [0.0], "model", "sync")

    assert [c.chunk_id for c in out] == ["v"]
    assert calls == {"vector": True, "rec_cosine": True}


def test_retrieve_for_ask_lexical_mode(monkeypatch):
    calls: dict[str, bool] = {}
    monkeypatch.setattr(main, "retrieve_top_k_lexical", lambda *a, **k: (calls.setdefault("lexical", True), [_rc("l", 0.05)])[1])
    monkeypatch.setattr(main, "record_lexical_scores", lambda *a, **k: calls.setdefault("rec_lexical", True))
    monkeypatch.setattr(main, "retrieve_top_k", lambda *a, **k: calls.setdefault("vector", True))
    monkeypatch.setattr(main, "record_retrieval_scores", lambda *a, **k: calls.setdefault("rec_cosine", True))

    req = AskRequest(question="q", retrieval_mode="lexical")
    out = main._retrieve_for_ask(None, req, [0.0], "model", "sync")

    assert [c.chunk_id for c in out] == ["l"]
    assert calls == {"lexical": True, "rec_lexical": True}  # cosine metric untouched


def test_retrieve_for_ask_hybrid_mode(monkeypatch):
    calls: dict[str, object] = {}
    fused = [
        FusedHit(chunk=_rc("h", 0.03), rrf_score=0.03, cosine_score=0.8, lexical_score=0.05),
        FusedHit(chunk=_rc("x", 0.02), rrf_score=0.02, cosine_score=None, lexical_score=0.04),
    ]
    monkeypatch.setattr(main, "retrieve_top_k_hybrid", lambda *a, **k: (calls.setdefault("hybrid", True), fused)[1])

    def fake_record_hybrid(endpoint, cosine, lexical, rrf):
        calls["rec_hybrid"] = (cosine, lexical, rrf)

    monkeypatch.setattr(main, "record_hybrid_scores", fake_record_hybrid)
    monkeypatch.setattr(main, "record_retrieval_scores", lambda *a, **k: calls.setdefault("rec_cosine", True))

    req = AskRequest(question="q", retrieval_mode="hybrid")
    out = main._retrieve_for_ask(None, req, [0.0], "model", "sync")

    assert [c.chunk_id for c in out] == ["h", "x"]  # returns the fused chunks in order
    assert "hybrid" in calls
    # None components dropped before recording; rrf list keeps every hit
    assert calls["rec_hybrid"] == ([0.8], [0.05, 0.04], [0.03, 0.02])


# --- Default mode + adaptive "auto" routing --------------------------------


def test_ask_request_defaults_to_hybrid():
    assert AskRequest(question="q").retrieval_mode == "hybrid"


def test_resolve_auto_mode_short_query_is_lexical():
    assert resolve_auto_mode("torn shingles") == "lexical"


def test_resolve_auto_mode_quoted_query_is_lexical():
    assert resolve_auto_mode('find "hail damage" reports') == "lexical"


def test_resolve_auto_mode_natural_language_is_hybrid():
    assert resolve_auto_mode("what hail damage was found on roofs in Wyoming") == "hybrid"


def test_resolve_auto_mode_empty_is_hybrid():
    assert resolve_auto_mode("   ") == "hybrid"


def test_retrieve_for_ask_auto_mode_routes_to_hybrid(monkeypatch):
    calls: dict[str, object] = {}
    fused = [FusedHit(chunk=_rc("h", 0.03), rrf_score=0.03, cosine_score=0.8, lexical_score=0.05)]
    monkeypatch.setattr(main, "retrieve_top_k_hybrid", lambda *a, **k: (calls.setdefault("hybrid", True), fused)[1])
    monkeypatch.setattr(main, "record_hybrid_scores", lambda *a, **k: calls.setdefault("rec_hybrid", True))
    monkeypatch.setattr(main, "retrieve_top_k_lexical", lambda *a, **k: calls.setdefault("lexical", True))

    req = AskRequest(question="what hail damage was found in Wyoming", retrieval_mode="auto")
    out = main._retrieve_for_ask(None, req, [0.0], "model", "sync")

    assert [c.chunk_id for c in out] == ["h"]
    assert "hybrid" in calls and "lexical" not in calls


def test_retrieve_for_ask_auto_mode_routes_short_query_to_lexical(monkeypatch):
    calls: dict[str, object] = {}
    monkeypatch.setattr(main, "retrieve_top_k_lexical", lambda *a, **k: (calls.setdefault("lexical", True), [_rc("l", 0.05)])[1])
    monkeypatch.setattr(main, "record_lexical_scores", lambda *a, **k: calls.setdefault("rec_lexical", True))
    monkeypatch.setattr(main, "retrieve_top_k_hybrid", lambda *a, **k: calls.setdefault("hybrid", True))

    req = AskRequest(question="torn shingles", retrieval_mode="auto")
    out = main._retrieve_for_ask(None, req, [0.0], "model", "sync")

    assert [c.chunk_id for c in out] == ["l"]
    assert "lexical" in calls and "hybrid" not in calls
