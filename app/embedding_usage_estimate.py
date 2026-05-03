"""
Heuristics for comparing Verbiage ingest volume to OpenAI embedding usage dashboards.

Embeddings are billed on each chunk body sent to the API. We sum chunk character lengths;
token counts use ceil(len(chunk)/4) per chunk (~4 chars/token English heuristic from cost notes).
"""


def embedding_chars_total(chunk_contents: list[str]) -> int:
    """Total UTF-8 characters embedded (matches payload size passed to embed_many per chunk sum)."""
    return sum(len(c) for c in chunk_contents)


def embedding_tokens_estimate_chars_heuristic(chunk_contents: list[str]) -> int:
    """
    Rough billable tokenizer units for embedding input: sum of ceil(len(chunk)/4) per chunk.
    Compare to incremental embedding token usage after an ingest on the OpenAI usage page.
    """
    return sum((len(chunk) + 3) // 4 for chunk in chunk_contents)


def embedding_metering(chunk_contents: list[str]) -> tuple[int, int]:
    """Returns (embedding_chars_total, embedding_tokens_estimate)."""
    chars = embedding_chars_total(chunk_contents)
    toks = embedding_tokens_estimate_chars_heuristic(chunk_contents)
    return chars, toks
