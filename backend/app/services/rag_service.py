from fastapi import HTTPException

from app.services.llm_service import generate_answer as generate_llm_answer
from app.services.vector_service import similarity_search


def search_documents(query: str, k: int = 4):
    return similarity_search(query=query, k=k)


def generate_answer(query: str, k: int = 4):
    results = search_documents(query, k=k)

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
            "filename": doc.metadata.get("filename"),
            "chunk_index": doc.metadata.get("chunk_index"),
        }
        for doc in results
    ]

    return {
        "answer": answer,
        "sources": sources,
    }
