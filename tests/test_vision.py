"""Tests for vision analysis JSON parsing."""

from app.report_writer.vision import _parse_vision_response


def test_parse_vision_response_structured():
    raw = '{"has_damage": true, "observations": "Missing shingles on north slope."}'
    result = _parse_vision_response(raw)
    assert result["has_damage"] is True
    assert result["observations"] == "Missing shingles on north slope."
    assert result["caption"] == "Missing shingles on north slope."
    assert "model" in result


def test_parse_vision_response_no_damage_flag():
    raw = '{"has_damage": false, "observations": "No visible damage."}'
    result = _parse_vision_response(raw)
    assert result["has_damage"] is False
    assert result["observations"] == "No visible damage."


def test_parse_vision_response_malformed_fallback():
    raw = "Plain text description of roof condition."
    result = _parse_vision_response(raw)
    assert result["observations"] == raw
    assert result["caption"] == raw
    assert "has_damage" not in result


def test_parse_vision_response_invalid_json():
    raw = '{"has_damage": true, "observations":'
    result = _parse_vision_response(raw)
    assert result["observations"] == raw
    assert "has_damage" not in result
