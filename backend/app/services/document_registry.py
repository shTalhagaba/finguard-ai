from __future__ import annotations

import json
import shutil
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.config import get_settings

REGISTRY_FILENAME = "documents.json"
_LOCK = threading.Lock()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _registry_path() -> Path:
    settings = get_settings()
    settings.uploads_directory.mkdir(parents=True, exist_ok=True)
    return settings.uploads_directory / REGISTRY_FILENAME


@dataclass
class DocumentRecord:
    document_id: str
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
    return sha256(content).hexdigest()


def _default_registry() -> dict[str, Any]:
    return {"documents": []}


def load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return _default_registry()

    try:
        return json.loads(path.read_text())
    except Exception:
        return _default_registry()


def _save_registry(registry: dict[str, Any]) -> None:
    path = _registry_path()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(registry, indent=2, sort_keys=True))
    tmp_path.replace(path)


def list_documents() -> list[DocumentRecord]:
    registry = load_registry()
    return [DocumentRecord(**item) for item in registry.get("documents", [])]


def get_document(document_id: str) -> DocumentRecord | None:
    for document in list_documents():
        if document.document_id == document_id:
            return document
    return None


def find_document_by_hash(file_hash: str) -> DocumentRecord | None:
    for document in list_documents():
        if document.file_hash == file_hash:
            return document
    return None


def upsert_document(document: DocumentRecord) -> DocumentRecord:
    with _LOCK:
        registry = load_registry()
        documents = registry.get("documents", [])
        filtered = [item for item in documents if item.get("document_id") != document.document_id]
        filtered.append(asdict(document))
        registry["documents"] = filtered
        _save_registry(registry)
    return document


def update_document(document_id: str, **changes: Any) -> DocumentRecord:
    with _LOCK:
        registry = load_registry()
        documents = registry.get("documents", [])
        updated: list[dict[str, Any]] = []
        result: dict[str, Any] | None = None

        for item in documents:
            if item.get("document_id") == document_id:
                item = {**item, **changes, "updated_at": _utcnow()}
                result = item
            updated.append(item)

        if result is None:
            raise KeyError(document_id)

        registry["documents"] = updated
        _save_registry(registry)
        return DocumentRecord(**result)


def remove_document(document_id: str) -> DocumentRecord | None:
    with _LOCK:
        registry = load_registry()
        documents = registry.get("documents", [])
        remaining = []
        removed: dict[str, Any] | None = None

        for item in documents:
            if item.get("document_id") == document_id:
                removed = item
                continue
            remaining.append(item)

        registry["documents"] = remaining
        _save_registry(registry)

    if removed is None:
        return None
    return DocumentRecord(**removed)


def create_document_record(
    *,
    document_id: str,
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
    timestamp = _utcnow()
    return DocumentRecord(
        document_id=document_id,
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
