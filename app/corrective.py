"""Corrective retrieval helpers: soft-refuse detection and one deterministic rewrite.

Used by /ask (and measure) for study 1.3 rewrite-once — not a multi-step agent loop.
"""

from __future__ import annotations

# Exact canary from _ask_prompt_from_chunks; soft refuse means chunks were shown to the LLM.
SOFT_REFUSE_CANARY = "No source documents contain that information."


def is_soft_refuse(answer: str) -> bool:
    """True when the model used the soft-refuse canary (chunks existed but were irrelevant)."""
    text = (answer or "").strip().lower()
    return SOFT_REFUSE_CANARY.lower() in text


def rewrite_query_for_retry(question: str) -> str | None:
    """Build a report-phrasing retrieval query for one retry, or None if nothing useful.

    Maps user wording toward phrases common in the storm-report corpus so hybrid
    retrieval can recover negation / intact-condition docs that the original NL
    query missed. Returns None when no domain phrase applies (skip rewrite).
    """
    text = (question or "").strip()
    if not text:
        return None
    lower = text.lower()
    parts: list[str] = []

    if "intact roof tiles" in lower:
        parts.append("intact roof tiles")
    elif "intact" in lower and ("tile" in lower or "tiles" in lower):
        parts.append("The roof tiles were intact")

    if "no storm-created opening" in lower:
        parts.append("No storm-created opening was identified")
    elif "storm-created opening" in lower and (
        " no " in f" {lower}" or lower.startswith("no ") or "not " in lower
    ):
        parts.append("No storm-created opening was identified")

    if not parts:
        return None

    rewritten = ". ".join(parts)
    if rewritten.lower() == lower:
        return None
    return rewritten
