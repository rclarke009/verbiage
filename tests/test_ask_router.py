"""Tests for Ask query routing."""

from app.ask_router import format_nearby_storm_answer, resolve_ask_route
from app.models import ClaimContext


def test_resolve_auto_nearby_with_claim_context():
    ctx = ClaimContext(
        address="1060 Alton Road, Port Charlotte, FL",
        storm_id="ian-2022",
        latitude=26.976,
        longitude=-82.090,
    )
    route = resolve_ask_route(
        "Which places are closest that had the same storm?",
        "auto",
        ctx,
    )
    assert route == "nearby_storm"


def test_resolve_auto_rag_without_context():
    route = resolve_ask_route(
        "Which places are closest that had the same storm?",
        "auto",
        None,
    )
    assert route == "rag"


def test_resolve_explicit_nearby_storm():
    route = resolve_ask_route("list reports", "nearby_storm", None)
    assert route == "nearby_storm"


def test_format_nearby_storm_answer():
    rows = [
        ("doc1", "Engineering Report - 100 Maple Court", "100 Maple Court, Lakeside, FL", 2.5),
        ("doc2", "Engineering Report - 400 Willow Way", "400 Willow Way, Hillcrest, FL", 4.1),
    ]
    answer = format_nearby_storm_answer(
        rows,
        storm_label="Hurricane Ian",
        anchor_address="1060 Alton Road, Port Charlotte, FL",
    )
    assert "100 Maple Court" in answer
    assert "400 Willow Way" in answer
    assert "2.5 mi" in answer
