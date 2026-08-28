from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import uuid

from app.services.document_service import (
    extract_text_from_pdf,
    split_text_into_chunks
)

from app.services.rag_service import add_document_chunks


router = APIRouter(
    prefix="/api",
    tags=["Documents"]
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):

    # Only allow PDF files
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    # Generate unique filename
    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"

    file_path = UPLOAD_DIR / unique_filename

    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Extract text from PDF
    extracted_text = extract_text_from_pdf(str(file_path))

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from this PDF"
        )

    # Split text into chunks
    chunks = split_text_into_chunks(extracted_text)

    # Store chunks in ChromaDB
    chunks_stored = add_document_chunks(
        chunks=chunks,
        filename=file.filename
    )

    return {
        "message": "Document processed and stored successfully",
        "filename": file.filename,
        "stored_as": unique_filename,
        "characters_extracted": len(extracted_text),
        "chunks_created": len(chunks),
        "chunks_stored": chunks_stored,
        "preview": chunks[0][:300] if chunks else ""
    }