from fastapi import HTTPException

from app.services.llm_service import generate_answer as generate_llm_answer
from app.services.vector_service import similarity_search


def search_documents(query: str, k: int = 4, document_id: str | None = None):
    return similarity_search(query=query, k=k, document_id=document_id)


def generate_answer(query: str, k: int = 4, document_id: str | None = None):
    results = search_documents(query, k=k, document_id=document_id)

    if not results:
        return {
            "answer": "I couldn't find relevant information in the uploaded documents.",
            "sources": [],
        }

    context = "\n\n---\n\n".join(
        f"Source: {doc.metadata.get('filename', 'Unknown')}\nContent: {doc.page_content}"
        for doc in results
    )

    try:
        answer = generate_llm_answer(context=context, question=query)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {exc}") from exc

    sources = [
        {
            "document_id": doc.metadata.get("document_id"),
            "filename": doc.metadata.get("filename"),
            "chunk_index": doc.metadata.get("chunk_index"),
            "stored_as": doc.metadata.get("stored_as"),
        }
        for doc in results
    ]

    return {
        "answer": answer,
        "sources": sources,
    }
