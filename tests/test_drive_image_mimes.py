"""Drive image MIME allowlist and HEIC normalization helpers."""

from unittest.mock import patch

from app.drive_client import IMAGE_MIMES, image_mime_query_clause, is_drive_image_mime
from app.report_writer.image_utils import (
    HEIC_MIMES,
    _looks_like_heic,
    normalize_image_bytes,
)


def test_image_mimes_includes_heic_and_heif():
    assert "image/jpeg" in IMAGE_MIMES
    assert "image/png" in IMAGE_MIMES
    assert "image/webp" in IMAGE_MIMES
    assert "image/heic" in IMAGE_MIMES
    assert "image/heif" in IMAGE_MIMES
    assert len(IMAGE_MIMES) == 5


def test_is_drive_image_mime():
    assert is_drive_image_mime("image/jpeg")
    assert is_drive_image_mime("image/heic")
    assert is_drive_image_mime("image/heif")
    assert not is_drive_image_mime("application/pdf")
    assert not is_drive_image_mime(None)
    assert not is_drive_image_mime("")


def test_image_mime_query_clause():
    clause = image_mime_query_clause()
    assert clause.startswith("(")
    assert clause.endswith(")")
    assert "mimeType = 'image/jpeg'" in clause
    assert "mimeType = 'image/heic'" in clause
    assert "mimeType = 'image/heif'" in clause
    assert " or " in clause


def test_looks_like_heic():
    heic_header = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00"
    assert _looks_like_heic(heic_header)
    assert not _looks_like_heic(b"\xff\xd8\xff\xe0")
    assert not _looks_like_heic(b"too short")


def test_normalize_image_bytes_passes_through_jpeg():
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 20
    out, mime = normalize_image_bytes(jpeg, "image/jpeg")
    assert out == jpeg
    assert mime == "image/jpeg"


def test_normalize_image_bytes_converts_heic_mime():
    raw = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00"
    converted = b"\xff\xd8converted"
    with patch("app.report_writer.image_utils.compress_image_bytes", return_value=(converted, "jpeg")):
        out, mime = normalize_image_bytes(raw, "image/heic")
    assert out == converted
    assert mime == "image/jpeg"


def test_normalize_image_bytes_converts_by_filename():
    raw = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00"
    converted = b"\xff\xd8converted"
    with patch("app.report_writer.image_utils.compress_image_bytes", return_value=(converted, "jpeg")):
        out, mime = normalize_image_bytes(raw, "application/octet-stream", filename="IMG_1234.HEIC")
    assert out == converted
    assert mime == "image/jpeg"


def test_heic_mimes_constant_matches_drive_allowlist():
    for mime in HEIC_MIMES:
        assert mime in IMAGE_MIMES
