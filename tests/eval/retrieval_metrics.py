"""Offline retrieval metrics: labeled recall@k / hit@k / MRR over unique doc_ids.

Pure functions. Safe to import from normal pytest (no Docker, no LLM, no VERBIAGE_EVAL).
Unanswerable questions have an empty relevant set; those scores are undefined (None)
so a zero is never confused with “we measured and missed.”
"""

from __future__ import annotations

from collections.abc import Sequence


def unique_ids(ids: Sequence[str]) -> list[str]:
    """Preserve first-occurrence order; drop later duplicates."""
    seen: set[str] = set()
    out: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def unique_doc_ids(chunks: Sequence[object]) -> list[str]:
    """First-occurrence unique ``doc_id`` from RetrievedChunk-like objects."""
    return unique_ids([getattr(c, "doc_id") for c in chunks])


def _cutoff(retrieved_ids: Sequence[str], k: int | None) -> list[str]:
    ranked = unique_ids(retrieved_ids)
    if k is None:
        return ranked
    return ranked[: max(k, 0)]


def recall_at(
    retrieved_ids: Sequence[str],
    relevant_ids: Sequence[str],
    k: int | None = None,
) -> float | None:
    """Fraction of gold docs appearing in the first *k* unique retrieved doc_ids.

    ``k=None`` scores the whole list (recall@pool when the list is the candidate pool).
    Returns None when there are no gold docs.
    """
    gold = unique_ids(relevant_ids)
    if not gold:
        return None
    ranked = set(_cutoff(retrieved_ids, k))
    return sum(1 for g in gold if g in ranked) / len(gold)


def hit_at(
    retrieved_ids: Sequence[str],
    relevant_ids: Sequence[str],
    k: int | None = None,
) -> float | None:
    """1.0 if any gold doc is in the cutoff, else 0.0. None when there is no gold."""
    gold = unique_ids(relevant_ids)
    if not gold:
        return None
    ranked = set(_cutoff(retrieved_ids, k))
    return 1.0 if any(g in ranked for g in gold) else 0.0


def mrr(
    retrieved_ids: Sequence[str],
    relevant_ids: Sequence[str],
    k: int | None = None,
) -> float | None:
    """Mean Reciprocal Rank of the first gold doc (single query). None when no gold.

    Returns 0.0 when gold exists but none appear in the cutoff.
    """
    gold = set(unique_ids(relevant_ids))
    if not gold:
        return None
    for rank, doc_id in enumerate(_cutoff(retrieved_ids, k), start=1):
        if doc_id in gold:
            return 1.0 / rank
    return 0.0
