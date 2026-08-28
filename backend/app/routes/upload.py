from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.services.document_registry import (
    cleanup_document_artifacts,
    compute_file_hash,
    create_document_record,
    delete_file_safely,
    find_document_by_hash,
    get_document,
    list_documents,
    remove_document,
    update_document,
    upsert_document,
)
from app.services.document_service import (
    build_preview,
    extract_pages_from_pdf,
    extract_text_from_pdf,
    split_text_into_chunks,
)
from app.services.vector_service import add_document_chunks, delete_document_chunks


router = APIRouter(prefix="/api", tags=["Documents"])


def _document_to_payload(document):
    return {
        "document_id": document.document_id,
        "filename": document.filename,
        "stored_as": document.stored_as,
        "status": document.status,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "error": document.error,
        "characters_extracted": document.characters_extracted,
        "chunks_created": document.chunks_created,
        "chunks_stored": document.chunks_stored,
        "preview": document.preview,
    }


@router.get("/documents")
async def get_documents():
    return {"documents": [_document_to_payload(document) for document in list_documents()]}


@router.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    settings = get_settings()
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF file is required.")

    responses = []
    failures = []

    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            failures.append({"filename": file.filename or "unknown", "detail": "Only PDF files are allowed."})
            continue

        content = await file.read()
        if not content:
            failures.append({"filename": file.filename, "detail": "Uploaded file is empty."})
            continue

        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            failures.append(
                {
                    "filename": file.filename,
                    "detail": f"File too large. Maximum size is {settings.max_upload_size_mb} MB.",
                }
            )
            continue

        file_hash = compute_file_hash(content)
        existing = find_document_by_hash(file_hash)
        if existing:
            responses.append(
                {
                    "document_id": existing.document_id,
                    "filename": existing.filename,
                    "status": "duplicate",
                    "detail": "Document already ingested.",
                }
            )
            continue

        document_id = str(uuid.uuid4())
        stored_as = f"{document_id}.pdf"
        file_path = settings.uploads_directory / stored_as
        record = create_document_record(
            document_id=document_id,
            filename=file.filename,
            stored_as=stored_as,
            file_hash=file_hash,
            status="processing",
        )
        upsert_document(record)

        try:
            file_path.write_bytes(content)
            page_blocks = extract_pages_from_pdf(str(file_path))
            extracted_text = extract_text_from_pdf(str(file_path))
            if not extracted_text.strip():
                raise HTTPException(status_code=400, detail="Could not extract text from this PDF.")

            chunks = []
            for page in page_blocks:
                page_chunks = split_text_into_chunks(str(page["text"]))
                for chunk in page_chunks:
                    chunk.setdefault("metadata", {})
                    chunk["metadata"] = {
                        **dict(chunk["metadata"]),
                        "page_number": page["page_number"],
                    }
                    chunks.append(chunk)

            chunks_stored = add_document_chunks(
                chunks=chunks,
                document_id=document_id,
                filename=file.filename,
                stored_as=stored_as,
            )
            preview = build_preview(extracted_text)
            updated = update_document(
                document_id,
                status="completed",
                characters_extracted=len(extracted_text),
                chunks_created=len(chunks),
                chunks_stored=chunks_stored,
                preview=preview,
                error=None,
            )
            responses.append(
                {
                    "message": "Document processed and stored successfully",
                    **_document_to_payload(updated),
                }
            )
        except HTTPException as exc:
            update_document(document_id, status="failed", error=exc.detail)
            delete_file_safely(file_path)
            failures.append({"filename": file.filename, "detail": exc.detail, "document_id": document_id})
        except Exception as exc:
            update_document(document_id, status="failed", error=str(exc))
            delete_file_safely(file_path)
            failures.append(
                {
                    "filename": file.filename,
                    "detail": f"Failed to process document: {exc}",
                    "document_id": document_id,
                }
            )

    if responses or failures:
        return {
            "documents": responses,
            "failures": failures,
        }

    raise HTTPException(status_code=500, detail="No files were processed.")


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        delete_document_chunks(document_id=document.document_id, chunk_count=document.chunks_stored)
    except Exception:
        pass

    cleanup_document_artifacts(document)
    remove_document(document_id)
    return {"message": "Document deleted successfully", "document_id": document_id}
