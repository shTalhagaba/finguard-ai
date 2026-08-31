from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.services.document_service import build_preview, extract_pages_from_pdf, extract_text_from_pdf, split_text_into_chunks


def _build_pdf_with_text(text: str) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    page = writer.pages[0]
    page.extract_text = lambda: text  # type: ignore[method-assign]
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_extraction_handles_real_pdf(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(_build_pdf_with_text("Policy content"))

    pages = extract_pages_from_pdf(str(pdf_path))
    assert isinstance(pages, list)


def test_pdf_text_extraction_returns_string(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(_build_pdf_with_text("Policy content"))

    text = extract_text_from_pdf(str(pdf_path))
    assert isinstance(text, str)


def test_chunking_produces_metadata():
    chunks = split_text_into_chunks("hello world " * 400)
    assert chunks
    assert all("text" in chunk for chunk in chunks)
    assert all("metadata" in chunk for chunk in chunks)


def test_build_preview_truncates():
    preview = build_preview("a" * 500, limit=20)
    assert preview == "a" * 20
