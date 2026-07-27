"""Resolve Drive photo folder IDs from claim property_metadata."""

from __future__ import annotations

from typing import Any


def normalize_drive_photo_folders(meta: dict | None) -> list[dict[str, str]]:
    """
    Return [{id, label}, ...] from drive_photo_folders or legacy single-id fields.
    """
    m = meta or {}
    raw = m.get("drive_photo_folders")
    if isinstance(raw, list):
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            fid = str(entry.get("id") or "").strip()
            if not fid or fid in seen:
                continue
            seen.add(fid)
            label = str(entry.get("label") or "").strip() or fid
            out.append({"id": fid, "label": label})
        return out

    legacy_id = str(m.get("drive_photo_folder_id") or "").strip()
    if not legacy_id:
        return []
    legacy_label = str(m.get("drive_photo_folder_label") or "").strip() or legacy_id
    return [{"id": legacy_id, "label": legacy_label}]


def resolve_drive_photo_folder_ids(meta: dict | None) -> list[str]:
    """Ordered unique folder IDs linked on the claim."""
    return [f["id"] for f in normalize_drive_photo_folders(meta)]


def mirror_drive_photo_folder_fields(folders: list[dict[str, str]]) -> dict[str, Any]:
    """Patch that sets drive_photo_folders plus legacy first-folder mirrors."""
    if not folders:
        return {
            "drive_photo_folders": [],
            "drive_photo_folder_id": "",
            "drive_photo_folder_label": "",
        }
    return {
        "drive_photo_folders": folders,
        "drive_photo_folder_id": folders[0]["id"],
        "drive_photo_folder_label": folders[0]["label"],
    }
