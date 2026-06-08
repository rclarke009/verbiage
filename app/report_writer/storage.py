"""Claim image storage (local filesystem or Supabase-compatible path)."""

from __future__ import annotations

import os
from pathlib import Path

from app.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

CLAIM_IMAGES_DIR = Path(os.getenv("CLAIM_IMAGES_DIR", "claim_images")).resolve()


def ensure_storage_dir() -> Path:
    CLAIM_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    return CLAIM_IMAGES_DIR


def storage_path_for(user_id: str, claim_id: str, image_id: str, filename: str) -> str:
    ext = Path(filename).suffix.lower() or ".jpg"
    return f"{user_id}/{claim_id}/{image_id}{ext}"


def write_claim_image(storage_path: str, data: bytes) -> None:
    base = ensure_storage_dir()
    dest = base / storage_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def read_claim_image_bytes(storage_path: str) -> bytes:
    base = ensure_storage_dir()
    return (base / storage_path).read_bytes()


def delete_claim_image_file(storage_path: str) -> None:
    base = ensure_storage_dir()
    path = base / storage_path
    if path.is_file():
        path.unlink()


def supabase_storage_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
