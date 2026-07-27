"""Unit tests for corrective rewrite-once helpers."""

from app.corrective import SOFT_REFUSE_CANARY, is_soft_refuse, rewrite_query_for_retry


def test_is_soft_refuse_matches_canary():
    assert is_soft_refuse(SOFT_REFUSE_CANARY)
    assert is_soft_refuse(f"  {SOFT_REFUSE_CANARY}  ")
    assert not is_soft_refuse("I don't have relevant context to answer that question.")
    assert not is_soft_refuse("412 Example Drive had intact roof tiles.")


def test_rewrite_tile_roof_no_storm_opening_gold_question():
    q = "Which tile-roof properties had intact roof tiles and no storm-created opening?"
    rewritten = rewrite_query_for_retry(q)
    assert rewritten is not None
    assert "intact roof tiles" in rewritten.lower()
    assert "no storm-created opening was identified" in rewritten.lower()


def test_rewrite_returns_none_without_domain_phrases():
    assert rewrite_query_for_retry("What is the weather in Paris?") is None
    assert rewrite_query_for_retry("") is None
