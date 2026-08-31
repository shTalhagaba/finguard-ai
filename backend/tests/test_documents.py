from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.document_service import (
    build_preview,
    extract_pages_from_pdf,
    extract_text_from_pdf,
    split_text_into_chunks,
)


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------


def test_pdf_extraction_returns_real_page_text(tmp_path, make_pdf):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(make_pdf("Policy content about identity verification."))

    pages = extract_pages_from_pdf(str(pdf_path))

    assert len(pages) == 1
    assert pages[0]["page_number"] == 1
    assert pages[0]["text"] == "Policy content about identity verification."


def test_pdf_extraction_skips_pages_without_text(tmp_path, make_pdf):
    pdf_path = tmp_path / "blank.pdf"
    pdf_path.write_bytes(make_pdf(""))

    pages = extract_pages_from_pdf(str(pdf_path))

    assert pages == []


def test_pdf_extraction_raises_400_for_corrupted_file(tmp_path):
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 not a real pdf body")

    with pytest.raises(HTTPException) as exc_info:
        extract_pages_from_pdf(str(pdf_path))

    assert exc_info.value.status_code == 400
    assert "Failed to read PDF" in exc_info.value.detail


def test_pdf_text_extraction_joins_pages(tmp_path, make_pdf):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(make_pdf("Refunds are allowed within 30 days."))

    text = extract_text_from_pdf(str(pdf_path))

    assert text == "Refunds are allowed within 30 days."


def test_pdf_text_extraction_empty_for_blank_pdf(tmp_path, make_pdf):
    pdf_path = tmp_path / "blank.pdf"
    pdf_path.write_bytes(make_pdf(""))

    text = extract_text_from_pdf(str(pdf_path))

    assert text == ""


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def test_chunking_produces_metadata_and_covers_all_content():
    text = "hello world " * 400
    chunks = split_text_into_chunks(text)

    assert chunks
    assert all("text" in chunk for chunk in chunks)
    assert all("metadata" in chunk for chunk in chunks)
    assert all(chunk["metadata"]["page_number"] == 1 for chunk in chunks)
    assert all(chunk["text"] for chunk in chunks)


def test_chunking_assigns_sequential_page_numbers_across_form_feeds():
    text = "First page content. " * 20 + "\f" + "Second page content. " * 20
    chunks = split_text_into_chunks(text)

    page_numbers = {chunk["metadata"]["page_number"] for chunk in chunks}
    assert page_numbers == {1, 2}


def test_chunking_empty_text_returns_no_chunks():
    assert split_text_into_chunks("") == []
    assert split_text_into_chunks("   ") == []


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def test_build_preview_truncates():
    preview = build_preview("a" * 500, limit=20)
    assert preview == "a" * 20


def test_build_preview_collapses_whitespace():
    preview = build_preview("hello   \n\n  world", limit=100)
    assert preview == "hello world"
