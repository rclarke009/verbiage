"""Tests for vision analysis JSON parsing and API retries."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.errors import LLMRateLimitedError, LLMServiceError
from app.report_writer.vision import _parse_vision_response, analyze_image_bytes


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


def _mock_response(status_code: int, *, json_body: dict | None = None, headers: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = ""
    resp.headers = headers or {}
    if json_body is not None:
        resp.json.return_value = json_body
    return resp


def test_analyze_image_bytes_retries_on_429():
    async def _run():
        success = _mock_response(
            200,
            json_body={
                "choices": [
                    {
                        "message": {
                            "content": '{"has_damage": false, "observations": "Clear roof."}',
                        }
                    }
                ]
            },
        )
        rate_limited = _mock_response(429, headers={"retry-after": "0.01"})

        client = MagicMock()
        client.post = AsyncMock(side_effect=[rate_limited, success])

        with (
            patch("app.report_writer.vision.OPENAI_API_KEY", "test-key"),
            patch("app.report_writer.vision.get_async_client", return_value=client),
            patch("app.report_writer.vision.normalize_image_bytes", return_value=(b"img", "image/jpeg")),
            patch("app.report_writer.vision.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await analyze_image_bytes(b"img", "image/jpeg")

        assert result["has_damage"] is False
        assert result["observations"] == "Clear roof."
        assert client.post.await_count == 2

    asyncio.run(_run())


def test_analyze_image_bytes_raises_after_exhausted_429_retries():
    async def _run():
        rate_limited = _mock_response(429)

        client = MagicMock()
        client.post = AsyncMock(return_value=rate_limited)

        with (
            patch("app.report_writer.vision.OPENAI_API_KEY", "test-key"),
            patch("app.report_writer.vision.LLM_MAX_ATTEMPTS", 2),
            patch("app.report_writer.vision.get_async_client", return_value=client),
            patch("app.report_writer.vision.normalize_image_bytes", return_value=(b"img", "image/jpeg")),
            patch("app.report_writer.vision.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(LLMRateLimitedError):
                await analyze_image_bytes(b"img", "image/jpeg")

        assert client.post.await_count == 2

    asyncio.run(_run())


def test_analyze_image_bytes_does_not_retry_other_4xx():
    async def _run():
        bad_request = _mock_response(400, json_body=None)
        bad_request.text = "bad request"

        client = MagicMock()
        client.post = AsyncMock(return_value=bad_request)

        with (
            patch("app.report_writer.vision.OPENAI_API_KEY", "test-key"),
            patch("app.report_writer.vision.get_async_client", return_value=client),
            patch("app.report_writer.vision.normalize_image_bytes", return_value=(b"img", "image/jpeg")),
        ):
            with pytest.raises(LLMServiceError):
                await analyze_image_bytes(b"img", "image/jpeg")

        assert client.post.await_count == 1

    asyncio.run(_run())


def test_analyze_image_bytes_retries_on_timeout():
    async def _run():
        success = _mock_response(
            200,
            json_body={
                "choices": [{"message": {"content": '{"has_damage": true, "observations": "Hail dents."}'}}]
            },
        )

        client = MagicMock()
        client.post = AsyncMock(side_effect=[httpx.TimeoutException("timed out"), success])

        with (
            patch("app.report_writer.vision.OPENAI_API_KEY", "test-key"),
            patch("app.report_writer.vision.get_async_client", return_value=client),
            patch("app.report_writer.vision.normalize_image_bytes", return_value=(b"img", "image/jpeg")),
            patch("app.report_writer.vision.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await analyze_image_bytes(b"img", "image/jpeg")

        assert result["has_damage"] is True
        assert client.post.await_count == 2

    asyncio.run(_run())
