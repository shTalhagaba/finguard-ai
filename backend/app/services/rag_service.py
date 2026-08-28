from __future__ import annotations

import re
from dataclasses import dataclass
from fastapi import HTTPException
from langchain_core.documents import Document

from app.config import get_settings
from app.services.llm_service import generate_answer as generate_llm_answer
from app.services.vector_service import similarity_search_with_scores


@dataclass
class RankedChunk:
    document: Document
    relevance_score: float
    rank_score: float


def preprocess_query(query: str) -> str:
    normalized = " ".join(query.split()).strip()
    normalized = re.sub(r"[^\w\s\-./]", " ", normalized)
    return " ".join(normalized.split())


def _chunk_signature(document: Document) -> str:
    metadata = document.metadata or {}
    return "|".join(
        [
            metadata.get("document_id", ""),
            str(metadata.get("page_number", "")),
            str(metadata.get("chunk_index", "")),
            re.sub(r"\s+", " ", document.page_content).strip().lower(),
        ]
    )


def _keyword_overlap(query: str, content: str) -> int:
    query_terms = {term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 2}
    if not query_terms:
        return 0
    content_terms = set(re.findall(r"[a-z0-9]+", content.lower()))
    return len(query_terms & content_terms)


def _rank_candidate(query: str, document: Document, relevance_score: float) -> float:
    overlap = _keyword_overlap(query, document.page_content)
    score = relevance_score if relevance_score is not None else 0.0
    score += min(overlap, 5) * 0.05
    metadata = document.metadata or {}
    if metadata.get("page_number") is not None:
        score += 0.01
    return score


def _format_context_entry(document: Document) -> str:
    metadata = document.metadata or {}
    page_number = metadata.get("page_number")
    source_bits = [metadata.get("filename", "Unknown")]
    if page_number is not None:
        source_bits.append(f"page {page_number}")
    header = "Source: " + ", ".join(source_bits)
    return f"{header}\nContent: {document.page_content}"


def _build_excerpt(content: str, limit: int = 240) -> str:
    normalized = " ".join(content.split()).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def _build_source_payload(document: Document, result: dict[str, object]) -> dict[str, object]:
    metadata = document.metadata or {}
    page_number = metadata.get("page_number")
    chunk_index = metadata.get("chunk_index")
    excerpt = _build_excerpt(document.page_content)

    return {
        "document": metadata.get("filename") or "Unknown document",
        "page": page_number,
        "chunk": {
            "index": chunk_index,
        },
        "excerpt": excerpt or None,
        "document_id": metadata.get("document_id"),
        "stored_as": metadata.get("stored_as"),
        "relevance_score": result["relevance_score"],
        "rank_score": result["rank_score"],
    }


def _clip_context(context_parts: list[str], max_chars: int) -> str:
    context = []
    total = 0
    for part in context_parts:
        part_length = len(part)
        separator_length = 2 if context else 0
        if total + separator_length + part_length > max_chars:
            break
        if context:
            context.append("\n\n")
            total += 2
        context.append(part)
        total += part_length
    return "".join(context)


def search_documents(query: str, k: int = 4, document_id: str | None = None) -> list[dict[str, object]]:
    settings = get_settings()
    processed_query = preprocess_query(query)
    initial_k = max(k, settings.retrieval_initial_k)
    try:
        raw_results = similarity_search_with_scores(query=processed_query, k=initial_k, document_id=document_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve documents: {exc}") from exc

    ranked: list[RankedChunk] = []
    seen: set[str] = set()

    for document, relevance_score in raw_results:
        if not document.page_content.strip():
            continue

        signature = _chunk_signature(document)
        if signature in seen:
            continue

        if relevance_score is not None and relevance_score < settings.retrieval_min_relevance_score:
            continue

        rank_score = _rank_candidate(processed_query, document, relevance_score or 0.0)
        if rank_score <= 0:
            continue

        seen.add(signature)
        ranked.append(RankedChunk(document=document, relevance_score=relevance_score or 0.0, rank_score=rank_score))

    ranked.sort(key=lambda item: item.rank_score, reverse=True)
    ranked = ranked[: min(k, settings.retrieval_max_results)]

    return [
        {
            "document": item.document,
            "relevance_score": round(item.relevance_score, 4),
            "rank_score": round(item.rank_score, 4),
        }
        for item in ranked
    ]


def generate_answer(query: str, k: int = 4, document_id: str | None = None):
    settings = get_settings()
    results = search_documents(query, k=k, document_id=document_id)

    if not results:
        return {
            "answer": "I couldn't find relevant information in the uploaded documents.",
            "sources": [],
        }

    context_parts: list[str] = []
    sources: list[dict[str, object]] = []

    for result in results:
        document: Document = result["document"]  # type: ignore[assignment]
        metadata = document.metadata or {}
        entry = _format_context_entry(document)
        context_parts.append(entry)
        sources.append(_build_source_payload(document, result))

    context = _clip_context(context_parts, settings.retrieval_max_context_chars)

    try:
        answer = generate_llm_answer(context=context, question=query)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {exc}") from exc

    return {
        "answer": answer,
        "sources": sources,
    }
