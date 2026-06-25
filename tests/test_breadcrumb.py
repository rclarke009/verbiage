"""Unit tests for document breadcrumb prefixes at index time."""

from app.breadcrumb import (
    apply_document_breadcrumb,
    build_document_breadcrumb_prefix,
    document_display_title,
)
from app.chunking import Chunk


def test_document_display_title_prefers_title():
    assert document_display_title("Roof Report", "roof.pdf", "doc-1") == "Roof Report"


def test_document_display_title_falls_back_to_filename():
    assert document_display_title(None, "roof.pdf", "doc-1") == "roof.pdf"


def test_document_display_title_falls_back_to_doc_id():
    assert document_display_title(None, None, "doc-1") == "doc-1"


def test_build_prefix_includes_document_and_source():
    prefix = build_document_breadcrumb_prefix(
        doc_id="abc",
        title="Hurricane Ian - Smith Residence",
        source="google_drive",
    )
    assert prefix == (
        "[Document: Hurricane Ian - Smith Residence]\n"
        "[Source: google_drive]"
    )


def test_build_prefix_omits_redundant_file_line():
    prefix = build_document_breadcrumb_prefix(
        doc_id="abc",
        title="Roof Report",
        source="upload",
        source_filename="Roof Report",
    )
    assert "[File:" not in prefix
    assert "[Document: Roof Report]" in prefix


def test_build_prefix_includes_file_when_different_from_title():
    prefix = build_document_breadcrumb_prefix(
        doc_id="abc",
        title="Smith Residence Roof",
        source="google_drive",
        source_filename="Smith_Residence_Roof.pdf",
    )
    assert "[File: Smith_Residence_Roof.pdf]" in prefix


def test_build_prefix_includes_location_and_storm():
    prefix = build_document_breadcrumb_prefix(
        doc_id="abc",
        title="Engineering Report - 1060 Alton Road",
        source="eval_fixture",
        address="1060 Alton Road, Port Charlotte, FL",
        storm_name="Ian",
    )
    assert "[Location: 1060 Alton Road, Port Charlotte, FL]" in prefix
    assert "[Storm: Ian]" in prefix


def test_apply_document_breadcrumb_prepends_to_each_chunk():
    chunks = [
        Chunk(
            chunk_index=0,
            content="[Section: Overview]\nDamage summary.",
            start_offset=0,
            end_offset=20,
            section_label="Overview",
        ),
        Chunk(
            chunk_index=1,
            content="[Section: Roof]\nMissing shingles.",
            start_offset=21,
            end_offset=40,
            section_label="Roof",
        ),
    ]
    prefix = "[Document: Roof Report]\n[Source: eval_fixture]"
    updated = apply_document_breadcrumb(chunks, prefix)

    assert updated[0].content.startswith("[Document: Roof Report]\n[Source: eval_fixture]\n\n")
    assert "[Section: Overview]" in updated[0].content
    assert updated[1].content.startswith("[Document: Roof Report]\n[Source: eval_fixture]\n\n")
    assert updated[0].start_offset == 0
    assert updated[0].section_label == "Overview"
