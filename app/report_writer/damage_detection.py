"""Classify vision analysis results for storm-damage evidence."""

from __future__ import annotations

_NO_DAMAGE_PHRASES = (
    "no visible damage",
    "no storm-related damage",
    "no storm related damage",
    "no apparent damage",
    "no observable damage",
    "does not show damage",
    "does not appear to show",
    "does not show any",
    "unable to determine",
    "unable to assess",
    "too unclear",
    "not visible",
    "no damage visible",
    "no evidence of damage",
    "without visible damage",
)

_DAMAGE_TERMS = (
    "damage",
    "deteriorat",
    "missing shingle",
    "missing tile",
    "torn",
    "crack",
    "puncture",
    "dent",
    "water stain",
    "water intrusion",
    "impact mark",
    "dislodged",
    "uplift",
    "hail",
    "fracture",
    "broken",
    "collapsed",
    "peeling",
    "blister",
)


def analysis_shows_damage(analysis: dict | None) -> bool:
    """Return True when analysis indicates observable storm-related damage."""
    if not analysis:
        return False
    if "has_damage" in analysis:
        return bool(analysis["has_damage"])
    text = (analysis.get("observations") or analysis.get("caption") or "").lower()
    if not text.strip():
        return False
    for phrase in _NO_DAMAGE_PHRASES:
        if phrase in text:
            return False
    return any(term in text for term in _DAMAGE_TERMS)


def count_photo_stats(images: list[dict]) -> dict[str, int]:
    """Count examined (succeeded) photos and those showing damage evidence."""
    examined = 0
    with_damage = 0
    for img in images:
        if (img.get("analysis_status") or "pending") != "succeeded":
            continue
        examined += 1
        if analysis_shows_damage(img.get("vision_analysis")):
            with_damage += 1
    return {"examined": examined, "with_damage": with_damage}


def photo_review_summary(examined: int, with_damage: int) -> str:
    """Sentence for report OBSERVATIONS when photos were reviewed."""
    if examined <= 0:
        return ""
    noun = "photograph" if examined == 1 else "photographs"
    verb = "was" if examined == 1 else "were"
    return (
        f"A total of {examined} inspection {noun} {verb} reviewed; "
        f"{with_damage} showed evidence of storm-related damage."
    )
