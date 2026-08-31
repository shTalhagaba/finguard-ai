from __future__ import annotations

import pytest
from fastapi import HTTPException
from langchain_core.documents import Document

from app.services import vector_service


class FakeVectorStore:
    """Stands in for langchain_chroma.Chroma so embedding/document wiring can
    be tested without a real Google API key or network access."""

    def __init__(self, search_results=None):
        self.added_documents: list[Document] = []
        self.added_ids: list[str] = []
        self.deleted_ids: list[str] = []
        self.search_calls: list[dict[str, object]] = []
        self._search_results = search_results or []

    def add_documents(self, documents, ids=None):
        self.added_documents.extend(documents)
        self.added_ids.extend(ids or [])

    def similarity_search_with_relevance_scores(self, query, k, filter=None):
        self.search_calls.append({"query": query, "k": k, "filter": filter})
        return self._search_results

    def delete(self, ids):
        self.deleted_ids.extend(ids)


# ---------------------------------------------------------------------------
# Embedding flow
# ---------------------------------------------------------------------------


def test_add_document_chunks_embeds_and_stores_with_metadata(monkeypatch):
    fake_store = FakeVectorStore()
    monkeypatch.setattr(vector_service, "get_vector_store", lambda: fake_store)

    chunks = [
        {"text": "Chunk one text", "metadata": {"page_number": 1}},
        {"text": "Chunk two text", "metadata": {"page_number": 1}},
    ]

    stored = vector_service.add_document_chunks(
        chunks=chunks,
        document_id="doc-1",
        user_id="user-1",
        filename="policy.pdf",
        stored_as="doc-1.pdf",
    )

    assert stored == 2
    assert fake_store.added_ids == ["doc-1:0", "doc-1:1"]
    assert len(fake_store.added_documents) == 2

    first = fake_store.added_documents[0]
    assert first.page_content == "Chunk one text"
    assert first.metadata["document_id"] == "doc-1"
    assert first.metadata["user_id"] == "user-1"
    assert first.metadata["filename"] == "policy.pdf"
    assert first.metadata["chunk_index"] == 0
    assert first.metadata["page_number"] == 1


def test_add_document_chunks_with_no_chunks_is_a_noop(monkeypatch):
    fake_store = FakeVectorStore()
    monkeypatch.setattr(vector_service, "get_vector_store", lambda: fake_store)

    stored = vector_service.add_document_chunks(
        chunks=[],
        document_id="doc-1",
        user_id="user-1",
        filename="policy.pdf",
        stored_as="doc-1.pdf",
    )

    assert stored == 0
    assert fake_store.added_documents == []


def test_delete_document_chunks_removes_stored_ids(monkeypatch):
    fake_store = FakeVectorStore()
    monkeypatch.setattr(vector_service, "get_vector_store", lambda: fake_store)

    vector_service.delete_document_chunks(document_id="doc-1", chunk_count=3)

    assert fake_store.deleted_ids == ["doc-1:0", "doc-1:1", "doc-1:2"]


def test_delete_document_chunks_skips_when_no_chunks_stored(monkeypatch):
    calls = []
    monkeypatch.setattr(vector_service, "get_vector_store", lambda: calls.append("called"))

    vector_service.delete_document_chunks(document_id="doc-1", chunk_count=0)

    assert calls == []


def test_similarity_search_with_scores_applies_document_and_user_filters(monkeypatch):
    hit = Document(page_content="KYC requires identity verification.", metadata={"document_id": "doc-1"})
    fake_store = FakeVectorStore(search_results=[(hit, 0.87)])
    monkeypatch.setattr(vector_service, "get_vector_store", lambda: fake_store)

    results = vector_service.similarity_search_with_scores(
        query="What is KYC?", k=3, document_id="doc-1", user_id="user-1"
    )

    assert results == [(hit, 0.87)]
    assert fake_store.search_calls[0]["filter"] == {"document_id": "doc-1", "user_id": "user-1"}
    assert fake_store.search_calls[0]["k"] == 3


# ---------------------------------------------------------------------------
# Missing API key
# ---------------------------------------------------------------------------


def test_get_embeddings_raises_http_exception_when_key_missing(monkeypatch):
    class StubSettings:
        google_api_key = None
        gemini_embedding_model = "models/gemini-embedding-001"

    monkeypatch.setattr(vector_service, "get_settings", lambda: StubSettings())
    vector_service.get_embeddings.cache_clear()

    try:
        with pytest.raises(HTTPException) as exc_info:
            vector_service.get_embeddings()
        assert exc_info.value.status_code == 500
        assert "GOOGLE_API_KEY" in exc_info.value.detail
    finally:
        vector_service.get_embeddings.cache_clear()
