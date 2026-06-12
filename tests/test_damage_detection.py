"""Tests for photo damage classification and stats."""

from app.report_writer.damage_detection import (
    analysis_shows_damage,
    count_photo_stats,
    photo_review_summary,
    select_export_images,
)


def test_analysis_shows_damage_structured_true():
    assert analysis_shows_damage({"has_damage": True, "observations": "nothing relevant"}) is True


def test_analysis_shows_damage_structured_false():
    assert analysis_shows_damage({"has_damage": False, "observations": "missing shingles"}) is False


def test_analysis_shows_damage_heuristic_no_damage_phrase():
    assert analysis_shows_damage({"observations": "No visible damage on the roof surface."}) is False


def test_analysis_shows_damage_heuristic_damage_terms():
    assert analysis_shows_damage({"caption": "Several missing shingles on north slope."}) is True


def test_analysis_shows_damage_empty():
    assert analysis_shows_damage(None) is False
    assert analysis_shows_damage({}) is False


def test_count_photo_stats():
    images = [
        {
            "analysis_status": "succeeded",
            "vision_analysis": {"has_damage": True},
        },
        {
            "analysis_status": "succeeded",
            "vision_analysis": {"has_damage": False},
        },
        {
            "analysis_status": "pending",
            "vision_analysis": {"has_damage": True},
        },
        {
            "analysis_status": "failed",
            "vision_analysis": {"has_damage": True},
        },
    ]
    assert count_photo_stats(images) == {"examined": 2, "with_damage": 1}


def test_photo_review_summary_singular():
    assert photo_review_summary(1, 1) == (
        "A total of 1 inspection photograph was reviewed; 1 showed evidence of storm-related damage."
    )


def test_photo_review_summary_plural():
    assert photo_review_summary(47, 12) == (
        "A total of 47 inspection photographs were reviewed; 12 showed evidence of storm-related damage."
    )


def test_photo_review_summary_zero_examined():
    assert photo_review_summary(0, 0) == ""


def test_select_export_images_damage_only_prefers_damage():
    images = [
        {"vision_analysis": {"has_damage": False}},
        {"vision_analysis": {"has_damage": True}, "image_id": "a"},
        {"vision_analysis": {"has_damage": True}, "image_id": "b"},
        {"vision_analysis": {"has_damage": False}},
    ]
    selected = select_export_images(images, max_photos=12, damage_only=True)
    assert len(selected) == 2
    assert all(analysis_shows_damage(img.get("vision_analysis")) for img in selected)


def test_select_export_images_damage_only_caps_at_max():
    images = [{"vision_analysis": {"has_damage": True}, "image_id": str(i)} for i in range(20)]
    selected = select_export_images(images, max_photos=12, damage_only=True)
    assert len(selected) == 12


def test_select_export_images_damage_only_empty_when_vision_ran_without_damage():
    images = [
        {"analysis_status": "succeeded", "vision_analysis": {"has_damage": False}},
        {"analysis_status": "succeeded", "vision_analysis": {"has_damage": False}},
    ]
    assert select_export_images(images, max_photos=12, damage_only=True) == []


def test_select_export_images_damage_only_fallback_when_vision_pending():
    images = [{"analysis_status": "pending", "image_id": str(i)} for i in range(20)]
    selected = select_export_images(images, max_photos=5, damage_only=True)
    assert len(selected) == 5
    assert selected[0]["image_id"] == "0"


def test_select_export_images_not_damage_only_orders_damage_first():
    images = [
        {"vision_analysis": {"has_damage": False}, "image_id": "clean"},
        {"vision_analysis": {"has_damage": True}, "image_id": "dmg"},
    ]
    selected = select_export_images(images, max_photos=12, damage_only=False)
    assert [img["image_id"] for img in selected] == ["dmg", "clean"]
