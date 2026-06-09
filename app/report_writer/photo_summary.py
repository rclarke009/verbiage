"""Condense many photo analyses into a prompt-friendly summary."""

from __future__ import annotations

MAX_SUMMARY_CHARS = 4000
INDIVIDUAL_PHOTO_THRESHOLD = 10


def _line_for_image(img: dict) -> str:
    cap = (img.get("caption") or "").strip()
    obs = (img.get("observations") or "").strip()
    name = (img.get("filename") or "").strip()
    text = cap or obs
    if not text:
        return ""
    prefix = f"[{name}] " if name else ""
    return f"- {prefix}{text}"


def build_photo_context_block(image_analyses: list[dict] | None) -> str:
    """
    Return text block for prompts. ≤10 photos: list individually; more: condensed summary.
    """
    if not image_analyses:
        return ""
    items = [img for img in image_analyses if _line_for_image(img)]
    if not items:
        return ""
    if len(items) <= INDIVIDUAL_PHOTO_THRESHOLD:
        lines = [_line_for_image(img) for img in items]
        return "Photo observations from this claim:\n" + "\n".join(lines) + "\n\n"
    return _build_summary(items)


def _build_summary(items: list[dict]) -> str:
    lines = [_line_for_image(img) for img in items]
    joined = "\n".join(lines)
    header = f"Photo observations from this claim ({len(items)} photos analyzed):\n"
    if len(header) + len(joined) + 2 <= MAX_SUMMARY_CHARS:
        return header + joined + "\n\n"
    # Truncate with note
    budget = MAX_SUMMARY_CHARS - len(header) - 80
    truncated = joined[:budget]
    if truncated and not truncated.endswith("\n"):
        truncated = truncated.rsplit("\n", 1)[0] + "\n"
    return (
        header
        + truncated
        + f"\n… ({len(items)} photos total; summary truncated for length)\n\n"
    )
