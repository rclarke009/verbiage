"""Image compression for report export."""

from __future__ import annotations

import io
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional at import; required at runtime for export
    Image = None  # type: ignore[misc, assignment]


def compress_image_bytes(data: bytes, *, max_dimension: int = 1200, quality: int = 80) -> tuple[bytes, str]:
    """Return JPEG bytes and file extension, resizing if needed."""
    if Image is None:
        ext = _guess_ext(data)
        return data, ext

    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, max_dimension / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue(), "jpeg"


def image_emu_size(data: bytes, *, width_inches: float = 3.5, max_height_inches: float = 4.0) -> tuple[int, int]:
    """Return cx, cy in EMU for DOCX embedding."""
    emu_per_inch = 914_400
    width_emu = int(width_inches * emu_per_inch)
    if Image is None:
        return width_emu, int(width_inches * emu_per_inch)

    with Image.open(io.BytesIO(data)) as img:
        w, h = img.size
        aspect = h / w if w else 1.0
        height_emu = int(width_emu * aspect)
        max_height_emu = int(max_height_inches * emu_per_inch)
        if height_emu > max_height_emu:
            height_emu = max_height_emu
        return width_emu, height_emu


def load_asset_bytes(name: str) -> bytes:
    path = Path(__file__).resolve().parent / "assets" / name
    return path.read_bytes()


def _guess_ext(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    return "jpeg"
