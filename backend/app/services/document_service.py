from pathlib import Path

from fastapi import HTTPException
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings


def extract_text_from_pdf(file_path: str) -> str:
    try:
        reader = PdfReader(file_path)
        text = []

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)

        return "\n".join(text).strip()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read PDF: {exc}") from exc


def split_text_into_chunks(text: str) -> list[str]:
    settings = get_settings()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    return text_splitter.split_text(text)
