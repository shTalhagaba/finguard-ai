from __future__ import annotations

import re
from dataclasses import dataclass
from fastapi import HTTPException
from langchain_core.documents import Document

from app.config import get_settings
from app.services.llm_service import generate_answer as generate_llm_answer
from app.services.llm_service import rewrite_query
from app.services.vector_service import similarity_search_with_scores


@dataclass
class RankedChunk:
    document: Document
    relevance_score: float
    rank_score: float


TASK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "kyc_policy_qa": ("kyc", "know your customer", "customer identification", "customer due diligence", "cdd"),
    "aml_policy_qa": ("aml", "anti money laundering", "anti-money laundering", "money laundering", "suspicious activity"),
    "transaction_policy_analysis": ("transaction policy", "transaction limit", "transfer limit", "wire", "domestic transfer", "international transfer"),
    "refund_policy_analysis": ("refund", "chargeback", "return period", "reversal"),
    "fraud_policy_qa": ("fraud", "fraud monitoring", "fraud detection", "alerts", "suspicious transaction"),
    "compliance_document_qa": ("compliance", "regulatory", "policy", "controls", "governance"),
    "policy_comparison": ("compare", "comparison", "difference between", "versus", "vs"),
    "extract_financial_limits": ("limit", "threshold", "maximum", "minimum", "cap", "ceiling"),
    "extract_fees": ("fee", "fees", "charges", "pricing", "commission"),
    "extract_important_dates": ("date", "deadline", "effective", "expiry", "expiration", "renewal", "review date"),
    "summarize_policies": ("summarize", "summary", "summarise", "briefly explain", "overview"),
    "explain_simple_language": ("simple language", "plain language", "easy to understand", "explain simply", "layman"),
}

TASK_ORDER = [
    "policy_comparison",
    "extract_financial_limits",
    "extract_fees",
    "extract_important_dates",
    "summarize_policies",
    "explain_simple_language",
    "kyc_policy_qa",
    "aml_policy_qa",
    "fraud_policy_qa",
    "transaction_policy_analysis",
    "refund_policy_analysis",
    "compliance_document_qa",
]


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


def _detect_task(query: str) -> str:
    normalized = query.lower()
    for task in TASK_ORDER:
        terms = TASK_KEYWORDS[task]
        if any(term in normalized for term in terms):
            return task
    return "general_policy_qa"


def _build_task_instructions(task: str) -> str:
    task_guidance = {
        "kyc_policy_qa": "Focus on KYC identity checks, onboarding controls, beneficial ownership, verification steps, documents required, and any exceptions or thresholds stated in the policies.",
        "aml_policy_qa": "Focus on AML monitoring, due diligence, sanctions screening, suspicious activity handling, escalation paths, and reporting requirements stated in the policies.",
        "transaction_policy_analysis": "Focus on transfer types, limits, caps, transaction rules, permitted channels, and conditions that change the effective limit.",
        "refund_policy_analysis": "Focus on refund eligibility, refund windows, reversal rules, chargebacks, exclusions, and any time-based conditions.",
        "fraud_policy_qa": "Focus on monitoring triggers, alert conditions, manual review steps, fraud indicators, and escalation or freeze procedures stated in the policies.",
        "compliance_document_qa": "Focus on compliance obligations, controls, ownership, audits, retention, escalation, and any formal requirements described in the documents.",
        "policy_comparison": "Compare the relevant policies or policy sections side by side. State similarities, differences, and any conflicting or more specific terms using only the context.",
        "extract_financial_limits": "Extract all monetary limits, thresholds, caps, and boundaries. Include currency, direction, scope, channel, and exceptions if present.",
        "extract_fees": "Extract all fees, charges, and pricing terms. Include amount, frequency, trigger, currency, and waiver or exemption conditions if present.",
        "extract_important_dates": "Extract deadlines, effective dates, cutoff dates, review dates, expiration dates, renewal periods, and any other important time limits.",
        "summarize_policies": "Summarize the policy clearly and compactly. Preserve the major obligations, limits, exceptions, and risk controls.",
        "explain_simple_language": "Rewrite the policy in plain language without changing the meaning. Keep it easy to understand and faithful to the source.",
        "general_policy_qa": "Answer the question directly from the uploaded policy text and stay anchored to the exact language when possible.",
    }
    return task_guidance.get(task, task_guidance["general_policy_qa"])


def build_task_profile(query: str) -> dict[str, str]:
    task = _detect_task(query)
    return {
        "task": task,
        "instructions": _build_task_instructions(task),
    }


def _format_chat_history(chat_history: list[dict[str, str]], max_turns: int = 6) -> str:
    recent_turns = chat_history[-max_turns:]
    lines: list[str] = []
    for turn in recent_turns:
        role = turn.get("role", "").strip().lower()
        content = " ".join(turn.get("content", "").split()).strip()
        if not role or not content:
            continue
        lines.append(f"{role.title()}: {content}")
    return "\n".join(lines)


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


def generate_answer(
    query: str,
    k: int = 4,
    document_id: str | None = None,
    chat_history: list[dict[str, str]] | None = None,
):
    settings = get_settings()
    task_profile = build_task_profile(query)
    history_text = _format_chat_history(chat_history or [], max_turns=6)
    contextualized_query = query
    if history_text:
        try:
            contextualized_query = rewrite_query(query=query, chat_history=history_text)
        except HTTPException:
            raise
        except Exception:
            contextualized_query = query

    retrieval_query = contextualized_query
    if task_profile["task"] in {"policy_comparison", "extract_financial_limits", "extract_fees", "extract_important_dates"}:
        retrieval_query = f"{contextualized_query} {task_profile['instructions']}"

    results = search_documents(retrieval_query, k=k, document_id=document_id)

    if not results:
        return {
            "answer": "I couldn't find relevant information in the uploaded documents.",
            "sources": [],
            "contextualized_query": contextualized_query,
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
        answer = generate_llm_answer(
            context=context,
            question=(
                f"Task: {task_profile['task']}\n"
                f"Guidance: {task_profile['instructions']}\n"
                f"User question: {contextualized_query}"
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {exc}") from exc

    return {
        "answer": answer,
        "sources": sources,
        "contextualized_query": contextualized_query,
        "task": task_profile["task"],
    }
