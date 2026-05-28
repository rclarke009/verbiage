"""
Google Drive read-only client for ingestion.
Uses OAuth2 with drive.readonly scope. Lists and fetches Google Docs, PDFs, and DOCX.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_DRIVE_DEFAULT_FOLDER_ID,
    GOOGLE_DRIVE_DEFAULT_FOLDER_LABEL,
    GOOGLE_REFRESH_TOKEN,
)
from app.docx_extract import extract_text_from_docx
from app.pdf_extract import extract_text_from_pdf

logger = logging.getLogger(__name__)

GOOGLE_DOCS_MIME = "application/vnd.google-apps.document"
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
EXPORT_MIME_PLAIN = "text/plain"

DRIVE_INGEST_MIMES: tuple[str, ...] = (
    GOOGLE_DOCS_MIME,
    PDF_MIME,
    DOCX_MIME,
)

MAX_DRIVE_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_FOLDER_PATH_DEPTH = 5

_DRIVE_FOLDER_IN_URL_RE = re.compile(r"/folders/([a-zA-Z0-9_-]+)")
_DRIVE_RAW_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_DRIVE_DOC_IN_URL_RE = re.compile(r"/document/d/|/file/d/")


def is_drive_ingestable_mime(mime_type: str | None) -> bool:
    """True when Drive file MIME is supported for list/ingest."""
    return (mime_type or "").strip() in DRIVE_INGEST_MIMES


def drive_mime_query_clause() -> str:
    """Drive API q fragment: (mimeType = '…' or …)."""
    parts = [f"mimeType = '{m}'" for m in DRIVE_INGEST_MIMES]
    return "(" + " or ".join(parts) + ")"


def drive_file_view_url(file_id: str) -> str:
    """Open link for PDF, DOCX, and other binary Drive files."""
    return f"https://drive.google.com/file/d/{file_id}/view"


def drive_google_doc_url(file_id: str) -> str:
    """Open link for native Google Docs."""
    return f"https://docs.google.com/document/d/{file_id}/edit"


def drive_source_url_for_mime(file_id: str, mime_type: str | None) -> str:
    """Preferred report URL for a Drive file by MIME type."""
    if mime_type == GOOGLE_DOCS_MIME:
        return drive_google_doc_url(file_id)
    return drive_file_view_url(file_id)


def parse_drive_folder_id(value: str | None) -> str | None:
    """
    Extract a Drive folder id from a raw id or folder URL.
    Returns None for empty input, document/file URLs, or unparseable values.
    """
    if not value or not value.strip():
        return None
    s = value.strip()
    if _DRIVE_DOC_IN_URL_RE.search(s) and not _DRIVE_FOLDER_IN_URL_RE.search(s):
        return None
    folder_match = _DRIVE_FOLDER_IN_URL_RE.search(s)
    if folder_match:
        return folder_match.group(1)
    if _DRIVE_RAW_ID_RE.fullmatch(s):
        return s
    return None


def resolve_drive_folder_id(explicit: str | None) -> str | None:
    """Use explicit folder when provided; otherwise env GOOGLE_DRIVE_DEFAULT_FOLDER_ID."""
    if explicit is not None and explicit.strip():
        return parse_drive_folder_id(explicit)
    if GOOGLE_DRIVE_DEFAULT_FOLDER_ID:
        return parse_drive_folder_id(GOOGLE_DRIVE_DEFAULT_FOLDER_ID)
    return None


def _drive_modified_to_unix(modified_time: str | None) -> int | None:
    """Parse Drive API RFC3339 modifiedTime to Unix seconds (UTC)."""
    if not modified_time:
        return None
    s = modified_time.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        return None


IndexStatus = Literal["not_indexed", "indexed", "stale"]


def compute_index_status(
    in_db: bool,
    drive_modified_unix: int | None,
    source_modified_at: int | None,
) -> IndexStatus:
    """Compare Drive modifiedTime to last-ingested source_modified_at."""
    if not in_db:
        return "not_indexed"
    if drive_modified_unix is None or source_modified_at is None:
        return "indexed"
    if drive_modified_unix > source_modified_at:
        return "stale"
    return "indexed"


@dataclass
class DriveDoc:
    """A document fetched from Drive, ready for ingest."""

    doc_id: str  # Drive file id (used as doc_id for idempotency)
    title: str
    text: str
    source: str = "google_drive"
    source_modified_at: int | None = None
    mime_type: str | None = None


class DriveClientError(Exception):
    """Raised when Drive API calls fail (auth, export, etc.)."""

    pass


def _get_credentials() -> Credentials:
    """Build Credentials from config; refresh if needed. Raises if config missing."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REFRESH_TOKEN:
        raise DriveClientError(
            "Google Drive credentials not configured. Set GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN (run one-time OAuth first)."
        )
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    try:
        creds.refresh(Request())
    except RefreshError as e:
        raise DriveClientError(
            f"Google refused the refresh token ({e!s}). "
            "Use the same GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET that created the token; "
            "check .env for stray quotes; revoke the app under Google Account → Security → "
            "Third-party access if needed, then open /auth/google again."
        ) from e
    return creds


def test_connection() -> bool:
    """
    Verify Drive credentials work with a minimal API call.
    Returns True on success. Raises DriveClientError on failure.
    """
    creds = _get_credentials()
    service = build("drive", "v3", credentials=creds)
    service.files().list(pageSize=1, fields="files(id)").execute()
    return True


def _folder_display_from_service(service, folder_id: str) -> dict:
    """Build folder breadcrumb using an existing Drive v3 service."""
    segments: list[str] = []
    current_id = folder_id
    visited: set[str] = set()
    for _ in range(MAX_FOLDER_PATH_DEPTH + 1):
        if current_id in visited:
            break
        visited.add(current_id)
        meta = (
            service.files()
            .get(
                fileId=current_id,
                fields="name,parents,mimeType",
                supportsAllDrives=True,
            )
            .execute()
        )
        name = (meta.get("name") or current_id).strip()
        segments.insert(0, name)
        parents = meta.get("parents") or []
        if not parents:
            break
        current_id = parents[0]
    folder_name = segments[-1] if segments else None
    path = " / ".join(segments) if segments else None
    return {"id": folder_id, "name": folder_name, "path": path}


def get_folder_display(folder_id: str) -> dict:
    """
    Return {id, name, path} for a Drive folder.
    path is a parent breadcrumb when available; name/path are None on API failure.
    """
    try:
        creds = _get_credentials()
        service = build("drive", "v3", credentials=creds)
        return _folder_display_from_service(service, folder_id)
    except Exception as e:
        logger.warning("Could not get folder display for %s: %s", folder_id, e)
        return {"id": folder_id, "name": None, "path": None}


def build_drive_folder_context(folder_id: str | None) -> dict | None:
    """Build UI folder context with display_path (env label for default inbox)."""
    if not folder_id:
        return None
    display = get_folder_display(folder_id)
    default_id = parse_drive_folder_id(GOOGLE_DRIVE_DEFAULT_FOLDER_ID)
    is_default = bool(default_id and folder_id == default_id)
    if is_default and GOOGLE_DRIVE_DEFAULT_FOLDER_LABEL:
        display_path = GOOGLE_DRIVE_DEFAULT_FOLDER_LABEL
    else:
        display_path = display.get("path") or display.get("name") or folder_id
    return {
        "id": folder_id,
        "name": display.get("name"),
        "path": display.get("path"),
        "is_default": is_default,
        "display_path": display_path,
    }


def list_docs_metadata(
    folder_id: str | None = None,
    file_ids: list[str] | None = None,
) -> list[dict]:
    """
    List ingestable Drive file metadata (no download). Google Docs, PDF, and DOCX.
    Returns list of dicts with id, name, mimeType, and optionally modifiedTime.
    """
    creds = _get_credentials()
    service = build("drive", "v3", credentials=creds)
    fields = "id, name, mimeType, modifiedTime"

    if file_ids:
        result: list[dict] = []
        for fid in file_ids:
            try:
                meta = (
                    service.files()
                    .get(fileId=fid, fields=fields)
                    .execute()
                )
                if is_drive_ingestable_mime(meta.get("mimeType")):
                    result.append(meta)
                else:
                    logger.warning(
                        "Skipping unsupported file %s (mimeType=%s)",
                        fid,
                        meta.get("mimeType"),
                    )
            except Exception as e:
                logger.warning("Could not get file %s: %s", fid, e)
        return result

    q_parts = [drive_mime_query_clause()]
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")
    q = " and ".join(q_parts)

    result = []
    page_token = None
    while True:
        resp = (
            service.files()
            .list(
                q=q,
                pageSize=100,
                fields=f"nextPageToken, files({fields})",
                pageToken=page_token,
            )
            .execute()
        )
        for f in resp.get("files", []):
            result.append(f)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return result


def _extract_text_from_bytes(mime_type: str, data: bytes, name: str) -> str:
    """Run MIME-appropriate text extraction on downloaded bytes."""
    try:
        if mime_type == PDF_MIME:
            return extract_text_from_pdf(data)
        if mime_type == DOCX_MIME:
            return extract_text_from_docx(data)
    except ValueError as e:
        raise DriveClientError(f"Could not extract text from {name}: {e}") from e
    raise DriveClientError(f"Unsupported mimeType for extraction: {mime_type}")


def _fetch_google_doc_text(service, file_id: str, name: str) -> str:
    try:
        content = service.files().export_media(
            fileId=file_id, mimeType=EXPORT_MIME_PLAIN
        ).execute()
        text = content.decode("utf-8") if isinstance(content, bytes) else content
        text = text.strip()
        if not text:
            raise DriveClientError(f"Empty export for {file_id} ({name})")
        return text
    except DriveClientError:
        raise
    except Exception as e:
        raise DriveClientError(f"Export failed for {name}: {e}") from e


def _download_drive_bytes(service, file_id: str, name: str) -> bytes:
    try:
        content = service.files().get_media(fileId=file_id).execute()
        if not isinstance(content, bytes):
            content = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        if len(content) > MAX_DRIVE_DOWNLOAD_BYTES:
            raise DriveClientError(
                f"File {name} exceeds max download size "
                f"({MAX_DRIVE_DOWNLOAD_BYTES // (1024 * 1024)} MB)"
            )
        return content
    except DriveClientError:
        raise
    except Exception as e:
        raise DriveClientError(f"Download failed for {name}: {e}") from e


def fetch_drive_file(file_id: str) -> DriveDoc:
    """
    Fetch a single ingestable Drive file and return text for ingest.
    Used by the async ingest worker.
    """
    creds = _get_credentials()
    service = build("drive", "v3", credentials=creds)
    try:
        meta = (
            service.files()
            .get(fileId=file_id, fields="id,name,mimeType,modifiedTime")
            .execute()
        )
    except Exception as e:
        raise DriveClientError(f"Could not get file {file_id}: {e}") from e

    mime_type = meta.get("mimeType")
    if not is_drive_ingestable_mime(mime_type):
        raise DriveClientError(
            f"File {file_id} is not an ingestable type (mimeType={mime_type})"
        )

    name = meta.get("name", file_id)
    modified_unix = _drive_modified_to_unix(meta.get("modifiedTime"))

    if mime_type == GOOGLE_DOCS_MIME:
        text = _fetch_google_doc_text(service, file_id, name)
    else:
        data = _download_drive_bytes(service, file_id, name)
        text = _extract_text_from_bytes(mime_type, data, name)

    return DriveDoc(
        doc_id=file_id,
        title=name or file_id,
        text=text,
        source="google_drive",
        source_modified_at=modified_unix,
        mime_type=mime_type,
    )


def list_and_export_docs(
    folder_id: str | None = None,
    file_ids: list[str] | None = None,
) -> list[DriveDoc]:
    """
    List Drive files and fetch text for ingest (sync path).

    - If file_ids is provided, only those files are considered (folder_id ignored).
    - If folder_id is provided and file_ids is None, list files in that folder.
    - If both None, list from root (q not restricted by parent).
    """
    metas = list_docs_metadata(folder_id=folder_id, file_ids=file_ids)
    result: list[DriveDoc] = []
    for meta in metas:
        fid = meta["id"]
        try:
            result.append(fetch_drive_file(fid))
        except DriveClientError:
            raise
    return result


def export_drive_doc(file_id: str) -> DriveDoc:
    """Backward-compatible alias for fetch_drive_file."""
    return fetch_drive_file(file_id)
