"""Report type validation for Report Writer API."""

from __future__ import annotations

from fastapi import HTTPException

from app.report_writer.constants import REPORT_TYPE_KEY, is_valid_report_type


def validate_report_type_metadata(property_metadata: dict | None, *, required: bool = False) -> None:
    meta = property_metadata or {}
    raw = (meta.get(REPORT_TYPE_KEY) or meta.get("report_template") or "").strip()
    if not raw:
        if required:
            raise HTTPException(
                status_code=400,
                detail="report_type is required (engineering, roof, or window_test)",
            )
        return
    if not is_valid_report_type(raw):
        raise HTTPException(
            status_code=400,
            detail="report_type must be engineering, roof, or window_test",
        )


def normalize_report_type_metadata(property_metadata: dict | None) -> dict:
    meta = dict(property_metadata or {})
    raw = (meta.get(REPORT_TYPE_KEY) or meta.get("report_template") or "").strip()
    if raw and is_valid_report_type(raw):
        meta[REPORT_TYPE_KEY] = raw
        meta.pop("report_template", None)
    return meta
