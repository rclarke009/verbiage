"""embedding_usage_estimate helpers match chunk payloads passed to embedding API."""

from app.chunking import chunk_text_chars
from app.embedding_usage_estimate import (
    embedding_chars_total,
    embedding_metering,
    embedding_tokens_estimate_chars_heuristic,
)


def test_empty_chunk_list():
    assert embedding_chars_total([]) == 0
    assert embedding_tokens_estimate_chars_heuristic([]) == 0
    assert embedding_metering([]) == (0, 0)


def test_single_short_chunk_four_chars_four_tokens_via_ceil_rule():
    # ceil(4/4)=1 token
    assert embedding_tokens_estimate_chars_heuristic(["abcd"]) == 1
    assert embedding_chars_total(["abcd"]) == 4


def test_single_chunk_five_chars_two_tokens_ceiled():
    # ceil(5/4)=2
    assert embedding_tokens_estimate_chars_heuristic(["abcde"]) == 2


def test_matches_summed_lengths_across_overlap_chunks():
    text = "a" * 2000  # multiple windows with overlap
    chunks = chunk_text_chars(text, 800, 100)
    contents = [c.content for c in chunks]
    chars, toks = embedding_metering(contents)
    assert chars == sum(len(x) for x in contents)
    assert toks == sum((len(x) + 3) // 4 for x in contents)
    assert len(chunks) >= 3
