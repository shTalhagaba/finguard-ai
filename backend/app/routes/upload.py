from pathlib import Path
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.services.document_service import extract_text_from_pdf, split_text_into_chunks
from app.services.vector_service import add_document_chunks


router = APIRouter(prefix="/api", tags=["Documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    settings = get_settings()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    file_extension = Path(file.filename).suffix or ".pdf"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = settings.uploads_directory / unique_filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb} MB.",
        )

    try:
        file_path.write_bytes(content)
        extracted_text = extract_text_from_pdf(str(file_path))

        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from this PDF.")

        chunks = split_text_into_chunks(extracted_text)
        chunks_stored = add_document_chunks(chunks=chunks, filename=file.filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {exc}") from exc

    return {
        "message": "Document processed and stored successfully",
        "filename": file.filename,
        "stored_as": unique_filename,
        "characters_extracted": len(extracted_text),
        "chunks_created": len(chunks),
        "chunks_stored": chunks_stored,
        "preview": chunks[0][:300] if chunks else "",
    }
