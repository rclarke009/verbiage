"""LLM client temperature plumbing.

These guard the recently-added temperature behaviour: production /ask falls back to
the configured LLM_TEMPERATURE (a low default), while callers (notably the eval
harness) can pin an explicit value for reproducibility. The HTTP layer is mocked, so
no network or live model is needed -- we only assert the value that reaches the
provider request payload.
"""

import asyncio

import httpx

import app.llm_client as llm
from app.config import LLM_TEMPERATURE


class _FakeResp:
    def __init__(self, payload: dict):
        self.status_code = 200
        self.headers = {}
        self.text = ""
        self._payload = payload

    def json(self):
        return self._payload


def _capture_post(monkeypatch, captured: dict, response_payload: dict):
    async def fake_post(self, *args, **kwargs):
        captured["payload"] = kwargs.get("json")
        return _FakeResp(response_payload)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)


# --- OpenAI path -----------------------------------------------------------

_OPENAI_OK = {"choices": [{"message": {"content": "ok"}}]}


def test_openai_uses_configured_temperature_by_default(monkeypatch):
    monkeypatch.setattr(llm, "OPENAI_API_KEY", "test-key")
    captured: dict = {}
    _capture_post(monkeypatch, captured, _OPENAI_OK)

    out = asyncio.run(llm.answer_with_context("prompt"))

    assert out == "ok"
    assert captured["payload"]["temperature"] == LLM_TEMPERATURE


def test_openai_explicit_temperature_overrides(monkeypatch):
    monkeypatch.setattr(llm, "OPENAI_API_KEY", "test-key")
    captured: dict = {}
    _capture_post(monkeypatch, captured, _OPENAI_OK)

    asyncio.run(llm.answer_with_context("prompt", temperature=0.0))

    # The eval harness relies on this exact pass-through for reproducible scoring.
    assert captured["payload"]["temperature"] == 0.0


# --- Ollama path -----------------------------------------------------------

_OLLAMA_OK = {"message": {"content": "ok"}}


def test_ollama_sets_temperature_option(monkeypatch):
    monkeypatch.setattr(llm, "OPENAI_API_KEY", "")  # force the local path
    captured: dict = {}
    _capture_post(monkeypatch, captured, _OLLAMA_OK)

    out = asyncio.run(llm.answer_with_context("prompt", temperature=0.0))

    assert out == "ok"
    assert captured["payload"]["options"]["temperature"] == 0.0


def test_ollama_defaults_to_configured_temperature(monkeypatch):
    monkeypatch.setattr(llm, "OPENAI_API_KEY", "")
    captured: dict = {}
    _capture_post(monkeypatch, captured, _OLLAMA_OK)

    asyncio.run(llm.answer_with_context("prompt"))

    assert captured["payload"]["options"]["temperature"] == LLM_TEMPERATURE


def test_ollama_null_message_returns_empty_string(monkeypatch):
    monkeypatch.setattr(llm, "OPENAI_API_KEY", "")
    _capture_post(monkeypatch, {}, {"message": None})

    out = asyncio.run(llm.answer_with_context("prompt"))

    assert out == ""
