from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def backend_env(monkeypatch, tmp_path_factory):
    data_root = tmp_path_factory.mktemp("finguard-backend")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-signing-key-test-signing-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
    monkeypatch.setenv("DATA_DIRECTORY", str(data_root / "data"))
    monkeypatch.setenv("UPLOADS_DIRECTORY", str(data_root / "uploads"))
    monkeypatch.setenv("CHROMA_PERSIST_DIRECTORY", str(data_root / "chroma"))

    import app.config

    app.config.get_settings.cache_clear()
    yield
    app.config.get_settings.cache_clear()
