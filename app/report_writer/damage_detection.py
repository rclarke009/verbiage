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


def _has_succeeded_analysis(img: dict) -> bool:
    return (img.get("analysis_status") or "pending") == "succeeded" or bool(img.get("vision_analysis"))


def select_export_images(
    images: list[dict],
    *,
    max_photos: int,
    damage_only: bool = True,
) -> list[dict]:
    """Pick photos to embed in PDF/DOCX export.

    When ``damage_only`` is true and any photo shows damage, only those are included (up to
    ``max_photos``). If vision has run but none show damage, no photos are embedded. When
    vision has not run yet, falls back to the first ``max_photos`` images so export still works.
    When ``damage_only`` is false, damage photos are listed first, then others, up to the cap.
    """
    if not images or max_photos <= 0:
        return []

    damage = [img for img in images if analysis_shows_damage(img.get("vision_analysis"))]

    if damage_only:
        if damage:
            return damage[:max_photos]
        if any(_has_succeeded_analysis(img) for img in images):
            return []
        return images[:max_photos]

    others = [img for img in images if img not in damage]
    return (damage + others)[:max_photos]


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
