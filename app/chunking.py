"""
Split text into overlapping chunks for embedding/retrieval.
Supports paragraph-first hybrid splitting (default) and legacy char windows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import ChunkingOptions

_SECTION_NUMBERED = re.compile(r"^\d+\.\s+[A-Z]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    """One chunk of text with indices into the original document."""

    chunk_index: int
    content: str
    start_offset: int
    end_offset: int
    section_label: str | None = None


def normalize_text(text: str) -> str:
    """Unify line endings and collapse excessive blank lines."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def is_section_header(paragraph: str) -> bool:
    """Lightweight heading detection for engineering reports."""
    line = paragraph.strip()
    if not line or len(line) > 80:
        return False
    if _SECTION_NUMBERED.match(line):
        return True
    if line.isupper() and len(line) >= 4 and not line.endswith("."):
        return True
    if line.endswith("."):
        return False
    words = line.split()
    if not words or len(words) > 12:
        return False
    if all(w[0].isupper() for w in words if w and w[0].isalpha()):
        return True
    return False


def chunk_text(text: str, options: ChunkingOptions) -> list[Chunk]:
    """Dispatch to strategy-specific chunker."""
    if options.strategy == "paragraph":
        return chunk_text_paragraph_hybrid(
            text, options.chunk_size, options.chunk_overlap
        )
    return chunk_text_chars(text, options.chunk_size, options.chunk_overlap)


def chunk_text_chars(text: str, chunk_size: int, overlap: int) -> list[Chunk]:
    """
    Split text into overlapping chunks. Step = chunk_size - overlap.
    Last chunk may be shorter. Overlap must be < chunk_size.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk size")

    list_of_chunks: list[Chunk] = []
    step = chunk_size - overlap
    for start in range(0, len(text), step):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunk_index = len(list_of_chunks)
        list_of_chunks.append(
            Chunk(
                chunk_index=chunk_index,
                content=chunk,
                start_offset=start,
                end_offset=end,
            )
        )
    return list_of_chunks


def _split_sentences(paragraph: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(paragraph.strip())
    return [p for p in parts if p]


def _sentence_chunks(
    paragraph: str,
    chunk_size: int,
    overlap: int,
    base_offset: int,
    section_label: str | None,
    start_index: int,
) -> list[Chunk]:
    """Split an oversized paragraph at sentence boundaries with overlap."""
    sentences = _split_sentences(paragraph)
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_len = 0
    chunk_start = base_offset

    def flush(end_offset: int) -> None:
        nonlocal chunk_start, current_parts, current_len
        if not current_parts:
            return
        body = " ".join(current_parts)
        content = body
        if section_label:
            content = f"[Section: {section_label}]\n{body}"
        chunks.append(
            Chunk(
                chunk_index=start_index + len(chunks),
                content=content,
                start_offset=chunk_start,
                end_offset=end_offset,
                section_label=section_label,
            )
        )

    pos = base_offset
    for sentence in sentences:
        sentence_len = len(sentence) + (1 if current_parts else 0)
        if current_parts and current_len + sentence_len > chunk_size:
            flush(pos)
            if overlap > 0 and chunks:
                tail = chunks[-1].content
                if section_label and tail.startswith("[Section:"):
                    _, _, tail = tail.partition("\n")
                overlap_text = tail[-overlap:] if len(tail) > overlap else tail
                current_parts = [overlap_text, sentence] if overlap_text else [sentence]
                current_len = sum(len(p) for p in current_parts) + max(0, len(current_parts) - 1)
                chunk_start = pos - len(overlap_text) if overlap_text else pos
            else:
                current_parts = [sentence]
                current_len = len(sentence)
                chunk_start = pos
        else:
            current_parts.append(sentence)
            current_len += sentence_len
        pos += len(sentence) + 1

    flush(base_offset + len(paragraph))
    return chunks


def _finalize_chunk_content(body: str, section_label: str | None) -> str:
    if section_label:
        return f"[Section: {section_label}]\n{body}"
    return body


def chunk_text_paragraph_hybrid(
    text: str, chunk_size: int, overlap: int
) -> list[Chunk]:
    """
    Paragraph-first chunking: merge paragraphs to target size, sentence-split
    oversized paragraphs, attach section labels from detected headers.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk size")

    normalized = normalize_text(text)
    if not normalized:
        return []

    raw_paragraphs = re.split(r"\n\n+", normalized)
    paragraphs: list[tuple[str, str | None, int, int]] = []
    current_section: str | None = None
    cursor = 0

    for raw in raw_paragraphs:
        para = raw.strip()
        if not para:
            continue
        para_start = normalized.find(para, cursor)
        if para_start < 0:
            para_start = cursor
        para_end = para_start + len(para)

        if is_section_header(para):
            current_section = para
            cursor = para_end
            continue

        paragraphs.append((para, current_section, para_start, para_end))
        cursor = para_end

    chunks: list[Chunk] = []
    buffer_parts: list[str] = []
    buffer_section: str | None = None
    buffer_start = 0
    buffer_end = 0

    def flush_buffer() -> None:
        nonlocal buffer_parts, buffer_section, buffer_start, buffer_end
        if not buffer_parts:
            return
        body = "\n\n".join(buffer_parts)
        if len(body) > chunk_size:
            sub = _sentence_chunks(
                body,
                chunk_size,
                overlap,
                buffer_start,
                buffer_section,
                len(chunks),
            )
            chunks.extend(sub)
        else:
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    content=_finalize_chunk_content(body, buffer_section),
                    start_offset=buffer_start,
                    end_offset=buffer_end,
                    section_label=buffer_section,
                )
            )
        buffer_parts = []
        buffer_section = None

    for para, section, p_start, p_end in paragraphs:
        if not buffer_parts:
            buffer_section = section
            buffer_start = p_start
            buffer_end = p_end
            buffer_parts = [para]
            continue

        candidate = "\n\n".join(buffer_parts + [para])
        if len(candidate) > chunk_size:
            flush_buffer()
            buffer_section = section
            buffer_start = p_start
            buffer_end = p_end
            buffer_parts = [para]
        else:
            buffer_parts.append(para)
            buffer_end = p_end

    flush_buffer()

    if not chunks and normalized:
        if len(normalized) > chunk_size:
            return _sentence_chunks(normalized, chunk_size, overlap, 0, None, 0)
        return [
            Chunk(
                chunk_index=0,
                content=normalized,
                start_offset=0,
                end_offset=len(normalized),
            )
        ]

    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i
    return chunks
