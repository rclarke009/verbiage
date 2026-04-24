"""Unit tests for fuzzy title matching (no DB)."""

from app.similar_titles import find_similar_titles, normalize_for_similarity, similarity_ratio


def test_normalize_strips_extension_and_whitespace():
    assert normalize_for_similarity("  Report_Final.PDF  ") == "report_final"
    assert normalize_for_similarity("foo.TXT") == "foo"


def test_similarity_exact_match():
    rows = [("a", "Storm Report 2024"), ("b", "Other")]
    m = find_similar_titles("Storm Report 2024.pdf", rows, min_ratio=0.82, limit=5)
    assert len(m) == 1
    assert m[0][0] == "a"
    assert m[0][2] == 1.0


def test_similarity_fuzzy_high():
    rows = [("x", "Acme Roof Inspection Jan 15")]
    m = find_similar_titles("Acme Roof Inspection Jan 15 (copy)", rows, min_ratio=0.82, limit=5)
    assert len(m) >= 1
    assert m[0][0] == "x"
    assert m[0][2] >= 0.82


def test_similarity_respects_limit():
    rows = [("1", "Report A"), ("2", "Report A v2"), ("3", "Report A final")]
    m = find_similar_titles("Report A", rows, min_ratio=0.5, limit=2)
    assert len(m) == 2


def test_similarity_empty_proposed():
    assert find_similar_titles("", [("1", "x")], min_ratio=0.82) == []


def test_similarity_ratio_helper():
    assert similarity_ratio("abc", "abc") == 1.0
    assert similarity_ratio("", "x") == 0.0
