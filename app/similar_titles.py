"""
Fuzzy matching of proposed document names against existing titles (advisory duplicate check).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_EXT_RE = re.compile(r"\.(pdf|txt|doc|docx)$", re.IGNORECASE)


def normalize_for_similarity(s: str) -> str:
    s = (s or "").lower().strip()
    s = _EXT_RE.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s


def similarity_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def find_similar_titles(
    proposed: str,
    doc_rows: list[tuple[str, str | None]],
    *,
    min_ratio: float = 0.82,
    limit: int = 5,
) -> list[tuple[str, str | None, float]]:
    """
    Return up to `limit` matches (doc_id, title, score) with score >= min_ratio.
    Compares normalized proposed string to each document's title, or doc_id if title empty.
    """
    norm_prop = normalize_for_similarity(proposed)
    if not norm_prop:
        return []
    matches: list[tuple[str, str | None, float]] = []
    for doc_id, title in doc_rows:
        label = (title or "").strip() or doc_id
        norm_label = normalize_for_similarity(label)
        if not norm_label:
            continue
        score = 1.0 if norm_prop == norm_label else similarity_ratio(norm_prop, norm_label)
        if score >= min_ratio:
            matches.append((doc_id, title, round(score, 4)))
    matches.sort(key=lambda x: (-x[2], (x[1] or x[0]).lower()))
    return matches[:limit]
