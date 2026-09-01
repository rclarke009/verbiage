"""Helpers for downloading original cited reports from Drive."""

from __future__ import annotations

import io
import os
import re
import zipfile
from urllib.parse import quote

from app.drive_client import download_drive_source_file

MAX_ZIP_DOCS = 20
_UNSAFE_FILENAME = re.compile(r'[/\\:\0<>"|?*]')


def is_drive_backed_source(source: str | None) -> bool:
    src_low = (source or "").lower()
    return "drive" in src_low or "google" in src_low


def safe_download_filename(name: str | None, fallback: str = "document") -> str:
    raw = (name or "").strip() or fallback
    raw = _UNSAFE_FILENAME.sub("_", raw)
    raw = raw.strip(" .")
    return (raw or fallback)[:180]


def content_disposition(filename: str) -> str:
    ascii_name = filename.encode("ascii", "replace").decode("ascii").replace('"', "_")
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'


def unique_zip_member(filename: str, used: set[str]) -> str:
    name = safe_download_filename(filename)
    if name not in used:
        used.add(name)
        return name
    stem, ext = os.path.splitext(name)
    i = 2
    while True:
        candidate = f"{stem}_{i}{ext}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        i += 1


def fetch_drive_source(doc_id: str, preferred_name: str | None) -> tuple[bytes, str, str]:
    """Returns (bytes, mime_type, download_filename). Raises DriveClientError."""
    return download_drive_source_file(doc_id, preferred_name)


def pack_sources_zip(files: list[tuple[str, bytes]], failures: list[str]) -> bytes:
    buf = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, data in files:
            member = unique_zip_member(filename, used)
            zf.writestr(member, data)
        if failures:
            zf.writestr("failed.txt", "\n".join(failures) + "\n")
    return buf.getvalue()
