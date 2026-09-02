"""Persisted report-editor layout on claim property_metadata."""

from __future__ import annotations

from typing import Any

from app.report_writer.constants import get_report_type, sections_for_type

LAYOUT_KEY = "document_layout"


def empty_layout(report_type: str | None = None, meta: dict | None = None) -> dict[str, Any]:
    type_id = report_type or "engineering"
    meta = meta or {}
    letter = str(meta.get("include_engineering_letter") or "").strip().lower()
    include_letter = letter in {"1", "true", "yes"} if letter else type_id == "engineering"
    return {
        "include_page_numbers": True,
        "include_address_footer": True,
        "include_engineering_letter": include_letter,
        "include_weather": True,
        "starting_page_number": 1,
        "section_order": [key for key, _ in sections_for_type(type_id)],
        "hidden_sections": [],
        "specimens": [],
        "photos": [],
    }


def get_layout(meta: dict | None) -> dict[str, Any]:
    raw = (meta or {}).get(LAYOUT_KEY)
    if isinstance(raw, dict) and raw:
        base = empty_layout(get_report_type(meta or {}), meta or {})
        merged = {**base, **raw}
        merged["specimens"] = list(raw.get("specimens") or [])
        merged["photos"] = list(raw.get("photos") or [])
        merged["hidden_sections"] = list(raw.get("hidden_sections") or [])
        merged["section_order"] = list(raw.get("section_order") or base["section_order"])
        return merged
    return empty_layout(get_report_type(meta or {}), meta or {})


def set_layout(meta: dict, layout: dict[str, Any]) -> dict:
    out = dict(meta or {})
    out[LAYOUT_KEY] = layout
    return out


def ensure_layout(meta: dict | None, *, images: list[dict] | None = None) -> dict[str, Any]:
    layout = get_layout(meta)
    existing_ids = {str(p.get("image_id") or "") for p in layout["photos"]}
    photos = list(layout["photos"])
    for idx, img in enumerate(images or []):
        image_id = str(img.get("image_id") or "")
        if not image_id or image_id in existing_ids:
            continue
        vision = img.get("vision_analysis") or {}
        caption = (vision.get("caption") or vision.get("observations") or "").strip()
        photos.append(
            {
                "image_id": image_id,
                "include": True,
                "caption": caption,
                "sort_order": img.get("sort_order") if img.get("sort_order") is not None else idx,
                "specimen_id": None,
            }
        )
        existing_ids.add(image_id)
    layout["photos"] = photos
    return layout


def photo_entry(layout: dict[str, Any], image_id: str) -> dict[str, Any] | None:
    for item in layout.get("photos") or []:
        if str(item.get("image_id") or "") == image_id:
            return item
    return None


def ordered_included_photos(layout: dict[str, Any], images: list[dict]) -> list[dict]:
    by_id = {str(img.get("image_id") or ""): img for img in images}
    entries = sorted(
        layout.get("photos") or [],
        key=lambda p: (int(p.get("sort_order") or 0), str(p.get("image_id") or "")),
    )
    out: list[dict] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.get("include") is False:
            continue
        image_id = str(entry.get("image_id") or "")
        img = by_id.get(image_id)
        if not img:
            continue
        merged = dict(img)
        caption = (entry.get("caption") or "").strip()
        if caption:
            vision = dict(merged.get("vision_analysis") or {})
            vision["caption"] = caption
            merged["vision_analysis"] = vision
        merged["_layout_caption"] = caption
        merged["_specimen_id"] = entry.get("specimen_id")
        out.append(merged)
        seen.add(image_id)
    if not entries:
        return images
    return out


def included_specimens(layout: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in (layout.get("specimens") or []) if s.get("include") is not False]


def section_keys_visible(layout: dict[str, Any], type_id: str) -> list[str]:
    hidden = {str(k) for k in (layout.get("hidden_sections") or [])}
    default = [key for key, _ in sections_for_type(type_id)]
    order = [str(k) for k in (layout.get("section_order") or [])]
    keys: list[str] = []
    for key in order:
        if key in hidden:
            continue
        if key in default and key not in keys:
            keys.append(key)
    for key in default:
        if key not in hidden and key not in keys:
            keys.append(key)
    return keys
