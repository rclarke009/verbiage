"""Unit tests for paragraph-first and char chunking."""

from app.chunking import (
    chunk_text,
    chunk_text_paragraph_hybrid,
    is_section_header,
    normalize_text,
)
from app.models import ChunkingOptions


def test_normalize_collapses_excessive_newlines():
    assert normalize_text("a\n\n\n\nb") == "a\n\nb"


def test_is_section_header_numbered():
    assert is_section_header("1. Overview")
    assert not is_section_header("This is a normal sentence.")


def test_is_section_header_all_caps():
    assert is_section_header("ROOF DAMAGE")
    assert not is_section_header("ab")


def test_paragraph_merge_multiple_short_paragraphs():
    text = "First paragraph about damage.\n\nSecond paragraph with more detail."
    chunks = chunk_text_paragraph_hybrid(text, 500, 50)
    assert len(chunks) == 1
    assert "First paragraph" in chunks[0].content
    assert "Second paragraph" in chunks[0].content


def test_section_header_sets_label():
    text = "2. Roof Damage\n\nShingles were missing on the north slope."
    chunks = chunk_text_paragraph_hybrid(text, 500, 50)
    assert len(chunks) >= 1
    assert chunks[0].section_label == "2. Roof Damage"
    assert "[Section: 2. Roof Damage]" in chunks[0].content


def test_long_paragraph_sentence_split():
    text = ". ".join(["Sentence number " + str(i) for i in range(40)]) + "."
    chunks = chunk_text_paragraph_hybrid(text, 400, 80)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.content) <= 550


def test_overlap_continuity_chars_strategy():
    text = "a" * 250
    opts = ChunkingOptions(strategy="chars", chunk_size=100, chunk_overlap=20)
    chunks = chunk_text(text, opts)
    assert len(chunks) >= 2
    assert chunks[0].end_offset - chunks[0].start_offset <= 100


def test_paragraph_strategy_via_chunk_text():
    text = "Intro line.\n\nMore details here."
    opts = ChunkingOptions(strategy="paragraph", chunk_size=500, chunk_overlap=50)
    chunks = chunk_text(text, opts)
    assert len(chunks) == 1
