from fastapi import HTTPException
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings


def extract_pages_from_pdf(file_path: str) -> list[dict[str, object]]:
    try:
        reader = PdfReader(file_path)
        pages: list[dict[str, object]] = []

        for index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            normalized = " ".join(page_text.split()).strip()
            if normalized:
                pages.append({"page_number": index, "text": normalized})

        return pages
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read PDF: {exc}") from exc


def extract_text_from_pdf(file_path: str) -> str:
    pages = extract_pages_from_pdf(file_path)
    return "\n".join(str(page["text"]) for page in pages).strip()


def split_text_into_chunks(text: str) -> list[dict[str, object]]:
    settings = get_settings()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max(settings.chunk_min_size, settings.chunk_size),
        chunk_overlap=min(settings.chunk_overlap, settings.chunk_size // 2),
    )

    pages = [page.strip() for page in text.split("\f") if page.strip()]
    if not pages:
        pages = [text.strip()] if text.strip() else []

    chunks: list[dict[str, object]] = []
    for page_index, page_text in enumerate(pages, start=1):
        for chunk_index, chunk in enumerate(text_splitter.split_text(page_text)):
            normalized = " ".join(chunk.split()).strip()
            if not normalized:
                continue
            chunks.append(
                {
                    "text": normalized,
                    "metadata": {
                        "page_number": page_index,
                        "page_chunk_index": chunk_index,
                    },
                }
            )

    return chunks


def build_preview(text: str, limit: int = 300) -> str:
    normalized = " ".join(text.split())
    return normalized[:limit]
