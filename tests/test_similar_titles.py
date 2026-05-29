"""Unit tests for fuzzy title matching (no DB)."""

from app.similar_titles import (
    find_similar_titles,
    normalize_for_similarity,
    parse_base_and_version,
    select_newest_versions,
    similarity_ratio,
)


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


def test_parse_base_and_version():
    assert parse_base_and_version("123 Main St Roof v10.pdf") == ("123 main st roof", 10)
    assert parse_base_and_version("123 Main St Roof v9.pdf") == ("123 main st roof", 9)
    assert parse_base_and_version("Report v.3.docx") == ("report", 3)
    assert parse_base_and_version("No Version Report.pdf") == ("no version report", None)


def test_select_newest_picks_v10_over_v9():
    # v10 must beat v9 by integer compare, not string ("v9" > "v10" lexically).
    files = [
        {"id": "a", "name": "123 Main St v9.pdf", "modifiedTime": "2026-01-01T00:00:00Z"},
        {"id": "b", "name": "123 Main St v10.pdf", "modifiedTime": "2026-01-01T00:00:00Z"},
    ]
    out = select_newest_versions(files)
    assert [f["id"] for f in out] == ["b"]


def test_select_newest_keeps_distinct_report_types():
    files = [
        {"id": "a", "name": "123 Main Roof v2.pdf", "modifiedTime": "2026-01-01T00:00:00Z"},
        {"id": "b", "name": "123 Main Siding v2.pdf", "modifiedTime": "2026-01-01T00:00:00Z"},
    ]
    out = select_newest_versions(files)
    assert {f["id"] for f in out} == {"a", "b"}


def test_select_newest_no_version_group_kept_intact():
    # Same base, no version tokens -> conservative: keep all, never drop silently.
    files = [
        {"id": "a", "name": "Quarterly Report.pdf", "modifiedTime": "2026-01-01T00:00:00Z"},
        {"id": "b", "name": "Quarterly Report.pdf", "modifiedTime": "2026-02-01T00:00:00Z"},
    ]
    out = select_newest_versions(files)
    assert {f["id"] for f in out} == {"a", "b"}


def test_select_newest_modified_time_tiebreak_within_version():
    # When version tokens tie, fall back to most recent modifiedTime.
    files = [
        {"id": "a", "name": "Report v3.pdf", "modifiedTime": "2026-01-01T00:00:00Z"},
        {"id": "b", "name": "Report v3.pdf", "modifiedTime": "2026-03-01T00:00:00Z"},
    ]
    out = select_newest_versions(files)
    assert [f["id"] for f in out] == ["b"]


def test_select_newest_collapses_pdf_and_docx_same_title():
    # Same report as both .pdf and .docx (no version): keep one, prefer docx.
    files = [
        {"id": "p", "name": "Storm Report.pdf", "mimeType": "application/pdf",
         "modifiedTime": "2026-01-01T00:00:00Z"},
        {"id": "d", "name": "Storm Report.docx",
         "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         "modifiedTime": "2026-01-01T00:00:00Z"},
    ]
    out = select_newest_versions(files)
    assert [f["id"] for f in out] == ["d"]


def test_select_newest_prefers_gdoc_over_docx_and_pdf():
    files = [
        {"id": "p", "name": "Roof Inspection.pdf", "mimeType": "application/pdf"},
        {"id": "g", "name": "Roof Inspection", "mimeType": "application/vnd.google-apps.document"},
        {"id": "d", "name": "Roof Inspection.docx",
         "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ]
    out = select_newest_versions(files)
    assert [f["id"] for f in out] == ["g"]


def test_select_newest_keeps_multiple_same_format_no_version():
    # Two genuinely distinct same-format files sharing a name are still both kept.
    files = [
        {"id": "a", "name": "Quarterly Report.pdf", "mimeType": "application/pdf",
         "modifiedTime": "2026-01-01T00:00:00Z"},
        {"id": "b", "name": "Quarterly Report.pdf", "mimeType": "application/pdf",
         "modifiedTime": "2026-02-01T00:00:00Z"},
    ]
    out = select_newest_versions(files)
    assert {f["id"] for f in out} == {"a", "b"}


def test_select_newest_format_dedup_falls_back_to_extension_without_mime():
    # No mimeType present (e.g. legacy callers) -> derive format from extension.
    files = [
        {"id": "p", "name": "Site Survey.pdf", "modifiedTime": "2026-01-01T00:00:00Z"},
        {"id": "d", "name": "Site Survey.docx", "modifiedTime": "2026-01-01T00:00:00Z"},
    ]
    out = select_newest_versions(files)
    assert [f["id"] for f in out] == ["d"]


def test_select_newest_preserves_order_and_empty_input():
    assert select_newest_versions([]) == []
    files = [
        {"id": "x", "name": "Alpha v1.pdf", "modifiedTime": "2026-01-01T00:00:00Z"},
        {"id": "y", "name": "Beta v1.pdf", "modifiedTime": "2026-01-01T00:00:00Z"},
    ]
    out = select_newest_versions(files)
    assert [f["id"] for f in out] == ["x", "y"]
