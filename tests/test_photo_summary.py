"""Tests for photo summary condensation."""

from app.report_writer.photo_summary import build_photo_context_block, INDIVIDUAL_PHOTO_THRESHOLD


def test_individual_photos_listed():
    items = [
        {"filename": f"p{i}.jpg", "caption": f"damage {i}", "observations": f"damage {i}"}
        for i in range(INDIVIDUAL_PHOTO_THRESHOLD)
    ]
    block = build_photo_context_block(items)
    assert "Photo observations" in block
    assert "damage 0" in block
    assert "damage 9" in block


def test_many_photos_summarized_or_truncated():
    items = [
        {"filename": f"p{i}.jpg", "caption": f"observation number {i} " * 20, "observations": ""}
        for i in range(50)
    ]
    block = build_photo_context_block(items)
    assert "50 photos" in block
    assert len(block) <= 4500
