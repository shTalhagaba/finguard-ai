from __future__ import annotations

import pytest
from fastapi import HTTPException

import app.config
from app.services import llm_service


def test_get_settings_succeeds_and_picks_up_google_api_key_from_env():
    app.config.get_settings.cache_clear()
    try:
        settings = app.config.get_settings()
        assert settings.google_api_key == "test-google-key"
    finally:
        app.config.get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Missing API key
# ---------------------------------------------------------------------------
#
# app.config.get_settings() does not itself validate that GOOGLE_API_KEY is
# present - it will happily build a Settings object with google_api_key=None.
# The failure surfaces lazily, the moment something tries to actually talk to
# Gemini: app.services.llm_service.get_llm() and
# app.services.vector_service.get_embeddings() (see test_vector_service.py)
# both guard against this explicitly.


def test_get_llm_raises_http_exception_when_key_missing(monkeypatch):
    class StubSettings:
        google_api_key = None
        gemini_chat_model = "gemini-2.5-flash"

    monkeypatch.setattr(llm_service, "get_settings", lambda: StubSettings())
    llm_service.get_llm.cache_clear()

    try:
        with pytest.raises(HTTPException) as exc_info:
            llm_service.get_llm()
        assert exc_info.value.status_code == 500
        assert "GOOGLE_API_KEY" in exc_info.value.detail
    finally:
        llm_service.get_llm.cache_clear()
