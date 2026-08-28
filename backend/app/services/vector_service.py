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


def add_document_chunks(chunks: list[str], filename: str) -> int:
    if not chunks:
        return 0

    vector_store = get_vector_store()
    documents = [
        Document(
            page_content=chunk,
            metadata={"filename": filename, "chunk_index": index},
        )
        for index, chunk in enumerate(chunks)
    ]
    vector_store.add_documents(documents)
    return len(documents)


def similarity_search(query: str, k: int = 4) -> list[Document]:
    return get_vector_store().similarity_search(query=query, k=k)
