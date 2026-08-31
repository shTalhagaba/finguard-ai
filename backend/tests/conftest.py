from __future__ import annotations

import io

import pytest


@pytest.fixture(autouse=True)
def backend_env(monkeypatch, tmp_path_factory):
    """Isolate every test: fake credentials, and data/uploads/chroma
    directories redirected into a throwaway tmp dir instead of the real
    backend/data, backend/uploads, backend/chroma_db used by the running app.

    This app's Settings resolves google_api_key/auth_signing_key from env
    vars at construction time (default_factory), but resolves its storage
    paths as fixed, non-overridable class defaults - so redirecting those
    requires mutating the cached Settings instance directly rather than
    setting env vars.
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-signing-key-test-signing-key")

    import app.config

    app.config.get_settings.cache_clear()
    settings = app.config.get_settings()

    data_root = tmp_path_factory.mktemp("finguard-backend")
    settings.chroma_persist_directory = data_root / "chroma"
    settings.uploads_directory = data_root / "uploads"
    settings.data_directory = data_root / "data"
    settings.chroma_persist_directory.mkdir(parents=True, exist_ok=True)
    settings.uploads_directory.mkdir(parents=True, exist_ok=True)
    settings.data_directory.mkdir(parents=True, exist_ok=True)

    yield
    app.config.get_settings.cache_clear()


def build_minimal_pdf(text: str) -> bytes:
    """Build a small, dependency-free single-page PDF with a real, extractable
    text layer (no reportlab/fpdf available in this environment). Writes a
    literal `Tj` text-showing operator into the page's content stream so
    pypdf's extract_text() returns genuine content instead of an empty page.
    """
    text_escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    content = f"BT /F1 18 Tf 72 720 Td ({text_escaped}) Tj ET"
    content_bytes = content.encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content_bytes)} >>\nstream\n".encode("latin-1") + content_bytes + b"\nendstream",
    ]

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode("latin-1"))
        buffer.write(obj)
        buffer.write(b"\nendobj\n")

    xref_offset = buffer.tell()
    count = len(objects) + 1
    buffer.write(f"xref\n0 {count}\n".encode("latin-1"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
    buffer.write(b"trailer\n")
    buffer.write(f"<< /Size {count} /Root 1 0 R >>\n".encode("latin-1"))
    buffer.write(b"startxref\n")
    buffer.write(f"{xref_offset}\n".encode("latin-1"))
    buffer.write(b"%%EOF")
    return buffer.getvalue()


@pytest.fixture
def make_pdf():
    """Factory fixture: make_pdf("some text") -> bytes of a real single-page PDF."""
    return build_minimal_pdf


@pytest.fixture
def sample_pdf_bytes(make_pdf):
    return make_pdf("FinGuard KYC Policy requires identity verification for all customers.")


@pytest.fixture
def blank_pdf_bytes(make_pdf):
    """A structurally valid PDF with no extractable text (empty content stream)."""
    return make_pdf("")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def register_user(client):
    def _register(email: str = "user@example.com", password: str = "correct-horse-battery", display_name: str = "Test User"):
        response = client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "display_name": display_name},
        )
        assert response.status_code == 200, response.text
        return response.json()

    return _register


@pytest.fixture
def auth_headers(register_user):
    payload = register_user()
    return {"Authorization": f"Bearer {payload['access_token']}"}
