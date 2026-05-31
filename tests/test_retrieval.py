"""Hybrid retrieval: RRF fusion (pure) and /ask mode routing (monkeypatched, no DB)."""

import asyncio

import pytest

import app.main as main
from app.config import RAG_MIN_RELEVANCE_SCORE
from app.models import AskRequest, RetrievedChunk
from app.retrieval import FusedHit, _rrf_fuse, lexical_query_text, resolve_auto_mode

_BELOW_GATE = RAG_MIN_RELEVANCE_SCORE - 0.1
_ABOVE_GATE = RAG_MIN_RELEVANCE_SCORE + 0.1


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
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert [c.chunk_id for c in out] == ["v"]
    assert calls == {"vector": True, "rec_cosine": True}


def test_retrieve_for_ask_lexical_mode(monkeypatch):
    calls: dict[str, bool] = {}
    monkeypatch.setattr(main, "retrieve_top_k_lexical", lambda *a, **k: (calls.setdefault("lexical", True), [_rc("l", 0.05)])[1])
    monkeypatch.setattr(main, "record_lexical_scores", lambda *a, **k: calls.setdefault("rec_lexical", True))
    monkeypatch.setattr(main, "retrieve_top_k", lambda *a, **k: calls.setdefault("vector", True))
    monkeypatch.setattr(main, "record_retrieval_scores", lambda *a, **k: calls.setdefault("rec_cosine", True))

    req = AskRequest(question="q", retrieval_mode="lexical")
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

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
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert [c.chunk_id for c in out] == ["h", "x"]  # returns the fused chunks in order
    assert "hybrid" in calls
    # None components dropped before recording; rrf list keeps every hit
    assert calls["rec_hybrid"] == ([0.8], [0.05, 0.04], [0.03, 0.02])


# --- Default mode + adaptive "auto" routing --------------------------------


def test_ask_request_defaults_to_auto():
    assert AskRequest(question="q").retrieval_mode == "auto"


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
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert [c.chunk_id for c in out] == ["h"]
    assert "hybrid" in calls and "lexical" not in calls


def test_retrieve_for_ask_auto_mode_routes_short_query_to_lexical(monkeypatch):
    calls: dict[str, object] = {}
    monkeypatch.setattr(main, "retrieve_top_k_lexical", lambda *a, **k: (calls.setdefault("lexical", True), [_rc("l", 0.05)])[1])
    monkeypatch.setattr(main, "record_lexical_scores", lambda *a, **k: calls.setdefault("rec_lexical", True))
    monkeypatch.setattr(main, "retrieve_top_k_hybrid", lambda *a, **k: calls.setdefault("hybrid", True))

    req = AskRequest(question="torn shingles", retrieval_mode="auto")
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert [c.chunk_id for c in out] == ["l"]
    assert "lexical" in calls and "hybrid" not in calls


# --- resolve_auto_mode branch + boundary coverage (table-driven) -----------


@pytest.mark.parametrize(
    "question, expected",
    [
        # real domain questions -- all natural language, so all route to hybrid
        ("which report had the hail damage in wyoming", "hybrid"),
        ("give me 3 text chunks about torn shingles", "hybrid"),
        ("Please provide text about water damage due to storm created opening", "hybrid"),
        # token boundary: <= 2 tokens is lexical, 3 flips to hybrid
        ("torn shingles", "lexical"),  # exactly at the 2-token limit
        ("torn shingles wyoming", "hybrid"),  # just over -> flips
        ("hail", "lexical"),  # single token
        ("WY-2024", "lexical"),  # identifier-style lookup
        # a balanced quoted phrase (single OR double) forces lexical regardless of length
        ('find "hail damage" reports', "lexical"),
        ("reports mentioning 'torn shingles' damage", "lexical"),
        ("\u201csmart quoted\u201d phrase in a long natural sentence", "lexical"),  # curly double quotes
        # contractions / possessives must NOT be mistaken for quoting -> stay hybrid
        ("what's the hail damage in wyoming", "hybrid"),
        ("what is the owner's roof claim about hail", "hybrid"),
        ("what\u2019s the storm damage in wyoming", "hybrid"),  # curly apostrophe
        # a lone / unbalanced quote is not a quoted phrase -> falls through to token count
        ('find " hail damage on the roof in wyoming', "hybrid"),
        # empty / whitespace-only -> hybrid (safe default)
        ("", "hybrid"),
        ("   ", "hybrid"),
    ],
)
def test_resolve_auto_mode_cases(question, expected):
    assert resolve_auto_mode(question) == expected


# --- lexical_query_text: search the quoted phrase, not the verbose wrapper ----


@pytest.mark.parametrize(
    "question, expected",
    [
        # verbose sentence wrapping a quoted phrase -> search only the phrase
        ("please provide text from a report about 'creased shingles'", "creased shingles"),
        ('find "hail damage" reports', "hail damage"),
        ("\u201ccreased shingles\u201d in this report", "creased shingles"),  # curly quotes
        # multiple quoted phrases are joined
        ('"a phrase" and "another phrase"', "a phrase another phrase"),
        # no quoted phrase -> returned unchanged
        ("torn shingles", "torn shingles"),
        ("what's the hail damage in wyoming", "what's the hail damage in wyoming"),
        ("", ""),
    ],
)
def test_lexical_query_text(question, expected):
    assert lexical_query_text(question) == expected


# --- lexical dispatch: phrase extraction + auto zero-hit fallback ------------


def test_retrieve_for_ask_lexical_searches_extracted_phrase(monkeypatch):
    captured: dict[str, object] = {}

    def fake_lexical(conn, query_text, top_k, doc_id=None):
        captured["text"] = query_text
        return [_rc("l", 0.05)]

    monkeypatch.setattr(main, "retrieve_top_k_lexical", fake_lexical)
    monkeypatch.setattr(main, "record_lexical_scores", lambda *a, **k: None)

    req = AskRequest(question="please give text about 'creased shingles'", retrieval_mode="lexical")
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert captured["text"] == "creased shingles"  # verbose wrapper stripped
    assert [c.chunk_id for c in out] == ["l"]


def test_retrieve_for_ask_auto_lexical_zero_hits_falls_back_to_hybrid(monkeypatch):
    calls: dict[str, object] = {}
    monkeypatch.setattr(main, "retrieve_top_k_lexical", lambda *a, **k: [])  # 0 lexical hits
    fused = [FusedHit(chunk=_rc("h", 0.03), rrf_score=0.03, cosine_score=0.8, lexical_score=0.05)]
    monkeypatch.setattr(main, "retrieve_top_k_hybrid", lambda *a, **k: (calls.setdefault("hybrid", True), fused)[1])
    monkeypatch.setattr(main, "record_hybrid_scores", lambda *a, **k: calls.setdefault("rec_hybrid", True))
    monkeypatch.setattr(main, "record_lexical_scores", lambda *a, **k: calls.setdefault("rec_lexical", True))

    # "torn shingles" resolves (via auto) to lexical; with 0 hits it must fall back
    req = AskRequest(question="torn shingles", retrieval_mode="auto")
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert [c.chunk_id for c in out] == ["h"]  # hybrid result
    assert "hybrid" in calls
    assert "rec_lexical" not in calls  # lexical metric not recorded on fallback


def test_retrieve_for_ask_explicit_lexical_zero_hits_does_not_fall_back(monkeypatch):
    calls: dict[str, object] = {}
    monkeypatch.setattr(main, "retrieve_top_k_lexical", lambda *a, **k: [])
    monkeypatch.setattr(main, "retrieve_top_k_hybrid", lambda *a, **k: calls.setdefault("hybrid", True))
    monkeypatch.setattr(main, "record_lexical_scores", lambda *a, **k: calls.setdefault("rec_lexical", True))

    req = AskRequest(question="nonexistent term", retrieval_mode="lexical")
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert out == []  # explicit lexical choice honored, even when empty
    assert "hybrid" not in calls
    assert "rec_lexical" in calls


# --- Relevance gate (cosine below threshold -> refuse) ---------------------


def test_relevance_gate_blocks_only_when_best_cosine_below_threshold():
    assert main._relevance_gate_blocks([]) is False  # no cosine signal -> never block
    assert main._relevance_gate_blocks([_BELOW_GATE, _BELOW_GATE]) is True
    assert main._relevance_gate_blocks([_BELOW_GATE, _ABOVE_GATE]) is False  # one strong hit clears it
    assert main._relevance_gate_blocks([RAG_MIN_RELEVANCE_SCORE]) is False  # boundary is inclusive


def test_retrieve_for_ask_vector_below_gate_returns_empty(monkeypatch):
    monkeypatch.setattr(main, "retrieve_top_k", lambda *a, **k: [_rc("v", _BELOW_GATE)])
    monkeypatch.setattr(main, "record_retrieval_scores", lambda *a, **k: None)

    req = AskRequest(question="off-corpus question", retrieval_mode="vector")
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert out == []  # weak cosine -> dropped so the prompt builder refuses


def test_retrieve_for_ask_hybrid_all_cosine_below_gate_returns_empty(monkeypatch):
    fused = [
        FusedHit(chunk=_rc("h", 0.03), rrf_score=0.03, cosine_score=_BELOW_GATE, lexical_score=0.05),
        FusedHit(chunk=_rc("x", 0.02), rrf_score=0.02, cosine_score=None, lexical_score=0.04),
    ]
    monkeypatch.setattr(main, "retrieve_top_k_hybrid", lambda *a, **k: fused)
    monkeypatch.setattr(main, "record_hybrid_scores", lambda *a, **k: None)

    req = AskRequest(question="off-corpus question", retrieval_mode="hybrid")
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert out == []  # best cosine is below the gate -> refuse


def test_retrieve_for_ask_lexical_never_gated_despite_low_score(monkeypatch):
    # Lexical scores are ts_rank, not cosine, so a low value must NOT trip the gate:
    # a lexical hit already means the query terms matched the document.
    monkeypatch.setattr(main, "retrieve_top_k_lexical", lambda *a, **k: [_rc("l", 0.01)])
    monkeypatch.setattr(main, "record_lexical_scores", lambda *a, **k: None)

    req = AskRequest(question="torn shingles", retrieval_mode="lexical")
    out = asyncio.run(main._retrieve_for_ask(None, req, [0.0], "model", "sync", None))

    assert [c.chunk_id for c in out] == ["l"]
