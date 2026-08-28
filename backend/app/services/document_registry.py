from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.db import db_transaction
from app.services.store import utcnow


@dataclass
class DocumentRecord:
    document_id: str
    user_id: str
    filename: str
    stored_as: str
    file_hash: str
    status: str
    created_at: str
    updated_at: str
    error: str | None = None
    characters_extracted: int = 0
    chunks_created: int = 0
    chunks_stored: int = 0
    preview: str = ""


def compute_file_hash(content: bytes) -> str:
    from hashlib import sha256

    return sha256(content).hexdigest()


def _row_to_record(row: Any) -> DocumentRecord:
    return DocumentRecord(**dict(row))


def list_documents(*, user_id: str) -> list[DocumentRecord]:
    with db_transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM documents WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [_row_to_record(row) for row in rows]


def get_document(document_id: str, *, user_id: str) -> DocumentRecord | None:
    with db_transaction() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE document_id = ? AND user_id = ?",
            (document_id, user_id),
        ).fetchone()
    return _row_to_record(row) if row else None


def find_document_by_hash(file_hash: str, *, user_id: str) -> DocumentRecord | None:
    with db_transaction() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE file_hash = ? AND user_id = ?",
            (file_hash, user_id),
        ).fetchone()
    return _row_to_record(row) if row else None


def upsert_document(document: DocumentRecord) -> DocumentRecord:
    with db_transaction() as conn:
        conn.execute(
            """
            INSERT INTO documents (
              document_id, user_id, filename, stored_as, file_hash, status,
              created_at, updated_at, error, characters_extracted,
              chunks_created, chunks_stored, preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
              filename=excluded.filename,
              stored_as=excluded.stored_as,
              file_hash=excluded.file_hash,
              status=excluded.status,
              updated_at=excluded.updated_at,
              error=excluded.error,
              characters_extracted=excluded.characters_extracted,
              chunks_created=excluded.chunks_created,
              chunks_stored=excluded.chunks_stored,
              preview=excluded.preview
            """,
            (
                document.document_id,
                document.user_id,
                document.filename,
                document.stored_as,
                document.file_hash,
                document.status,
                document.created_at,
                document.updated_at,
                document.error,
                document.characters_extracted,
                document.chunks_created,
                document.chunks_stored,
                document.preview,
            ),
        )
    return document


def update_document(document_id: str, *, user_id: str, **changes: Any) -> DocumentRecord:
    allowed_fields = {
        "filename",
        "stored_as",
        "file_hash",
        "status",
        "error",
        "characters_extracted",
        "chunks_created",
        "chunks_stored",
        "preview",
    }
    update_fields = {key: value for key, value in changes.items() if key in allowed_fields}
    if not update_fields:
        existing = get_document(document_id, user_id=user_id)
        if existing is None:
            raise KeyError(document_id)
        return existing

    update_fields["updated_at"] = utcnow()
    assignments = ", ".join(f"{key} = ?" for key in update_fields)
    params = list(update_fields.values()) + [document_id, user_id]
    with db_transaction() as conn:
        result = conn.execute(
            f"UPDATE documents SET {assignments} WHERE document_id = ? AND user_id = ?",
            tuple(params),
        )
        if result.rowcount == 0:
            raise KeyError(document_id)

    existing = get_document(document_id, user_id=user_id)
    if existing is None:
        raise KeyError(document_id)
    return existing


def remove_document(document_id: str, *, user_id: str) -> DocumentRecord | None:
    existing = get_document(document_id, user_id=user_id)
    if existing is None:
        return None
    with db_transaction() as conn:
        conn.execute(
            "DELETE FROM documents WHERE document_id = ? AND user_id = ?",
            (document_id, user_id),
        )
    return existing


def create_document_record(
    *,
    document_id: str,
    user_id: str,
    filename: str,
    stored_as: str,
    file_hash: str,
    status: str,
    characters_extracted: int = 0,
    chunks_created: int = 0,
    chunks_stored: int = 0,
    preview: str = "",
    error: str | None = None,
) -> DocumentRecord:
    timestamp = utcnow()
    return DocumentRecord(
        document_id=document_id,
        user_id=user_id,
        filename=filename,
        stored_as=stored_as,
        file_hash=file_hash,
        status=status,
        created_at=timestamp,
        updated_at=timestamp,
        error=error,
        characters_extracted=characters_extracted,
        chunks_created=chunks_created,
        chunks_stored=chunks_stored,
        preview=preview,
    )


def delete_file_safely(path: str | Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except TypeError:
        target = Path(path)
        if target.exists():
            target.unlink()


def cleanup_uploaded_file(path: str | Path) -> None:
    target = Path(path)
    if target.exists():
        target.unlink()


def cleanup_document_artifacts(document: DocumentRecord) -> None:
    cleanup_uploaded_file(get_settings().uploads_directory / document.stored_as)
