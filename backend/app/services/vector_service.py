from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.config import get_settings


@lru_cache(maxsize=1)
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    settings = get_settings()
    if not settings.google_api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY is not configured.")

    return GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embedding_model,
        google_api_key=settings.google_api_key,
    )


def get_vector_store() -> Chroma:
    settings = get_settings()
    return Chroma(
        collection_name="finguard_documents",
        embedding_function=get_embeddings(),
        persist_directory=str(settings.chroma_persist_directory),
    )


def add_document_chunks(
    *,
    chunks: list[dict[str, object]],
    document_id: str,
    user_id: str,
    filename: str,
    stored_as: str,
) -> int:
    if not chunks:
        return 0

    vector_store = get_vector_store()
    ids = [f"{document_id}:{index}" for index in range(len(chunks))]
    documents = [
        Document(
            page_content=str(chunk["text"]),
            metadata={
                "document_id": document_id,
                "user_id": user_id,
                "filename": filename,
                "stored_as": stored_as,
                "chunk_index": index,
                **dict(chunk.get("metadata", {})),
            },
        )
        for index, chunk in enumerate(chunks)
    ]
    vector_store.add_documents(documents, ids=ids)
    return len(documents)


def similarity_search(query: str, k: int = 4, document_id: str | None = None, user_id: str | None = None) -> list[Document]:
    filter_kwargs: dict[str, str] = {}
    if document_id:
        filter_kwargs["document_id"] = document_id
    if user_id:
        filter_kwargs["user_id"] = user_id
    return get_vector_store().similarity_search(query=query, k=k, filter=filter_kwargs or None)


def similarity_search_with_scores(
    query: str,
    k: int = 4,
    document_id: str | None = None,
    user_id: str | None = None,
) -> list[tuple[Document, float]]:
    vector_store = get_vector_store()
    filter_kwargs: dict[str, str] = {}
    if document_id:
        filter_kwargs["document_id"] = document_id
    if user_id:
        filter_kwargs["user_id"] = user_id

    if hasattr(vector_store, "similarity_search_with_relevance_scores"):
        return vector_store.similarity_search_with_relevance_scores(
            query=query,
            k=k,
            filter=filter_kwargs or None,
        )

    documents = vector_store.similarity_search(query=query, k=k, filter=filter_kwargs or None)
    return [(document, 0.0) for document in documents]


def delete_document_chunks(document_id: str, chunk_count: int) -> None:
    if chunk_count <= 0:
        return

    vector_store = get_vector_store()
    ids = [f"{document_id}:{index}" for index in range(chunk_count)]
    vector_store.delete(ids=ids)
