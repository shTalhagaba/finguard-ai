from __future__ import annotations

from langchain_core.documents import Document

from app.services import rag_service


def _doc(text: str, **metadata) -> Document:
    return Document(page_content=text, metadata=metadata)


# ---------------------------------------------------------------------------
# Document retrieval / ranking
# ---------------------------------------------------------------------------


def test_search_documents_filters_low_relevance_empty_and_duplicate_chunks(monkeypatch):
    kept = _doc(
        "KYC requires identity verification.",
        document_id="doc-1",
        page_number=1,
        chunk_index=0,
    )
    duplicate = _doc(
        "KYC requires identity verification.",
        document_id="doc-1",
        page_number=1,
        chunk_index=0,
    )
    below_threshold = _doc("irrelevant weather report", document_id="doc-2", page_number=1, chunk_index=0)
    empty_content = _doc("   ", document_id="doc-3", page_number=1, chunk_index=0)

    results = [
        (kept, 0.9),
        (duplicate, 0.9),
        (below_threshold, 0.05),
        (empty_content, 0.9),
    ]
    monkeypatch.setattr(rag_service, "similarity_search_with_scores", lambda **kwargs: results)

    ranked = rag_service.search_documents("What are the KYC requirements?", k=4)

    assert len(ranked) == 1
    assert ranked[0]["document"].metadata["document_id"] == "doc-1"


def test_search_documents_respects_document_and_user_scoping(monkeypatch):
    captured = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(rag_service, "similarity_search_with_scores", fake_search)

    rag_service.search_documents("refund window", k=2, document_id="doc-9", user_id="user-1")

    assert captured["document_id"] == "doc-9"
    assert captured["user_id"] == "user-1"


# ---------------------------------------------------------------------------
# Chat / unsupported questions / empty documents
# ---------------------------------------------------------------------------


def test_generate_answer_returns_fallback_when_no_documents_are_indexed(monkeypatch):
    monkeypatch.setattr(rag_service, "similarity_search_with_scores", lambda **kwargs: [])

    result = rag_service.generate_answer("What are the KYC requirements?", k=4)

    assert result["answer"] == "I couldn't find relevant information in the uploaded documents."
    assert result["sources"] == []


def test_generate_answer_returns_fallback_for_unsupported_question(monkeypatch):
    """A question with no topical overlap with any indexed policy should be
    treated the same as having no documents: nothing clears the relevance
    threshold, so the assistant declines rather than guessing."""
    off_topic = _doc("weather forecast for tomorrow", document_id="doc-1", page_number=1, chunk_index=0)
    monkeypatch.setattr(
        rag_service, "similarity_search_with_scores", lambda **kwargs: [(off_topic, 0.02)]
    )

    result = rag_service.generate_answer("What's the weather like on Mars?", k=4)

    assert result["answer"] == "I couldn't find relevant information in the uploaded documents."
    assert result["sources"] == []


# ---------------------------------------------------------------------------
# Hallucination protection
# ---------------------------------------------------------------------------


def test_generate_answer_never_calls_llm_without_grounding_context(monkeypatch):
    monkeypatch.setattr(rag_service, "similarity_search_with_scores", lambda **kwargs: [])

    llm_calls = []
    monkeypatch.setattr(
        rag_service,
        "generate_llm_answer",
        lambda **kwargs: llm_calls.append(kwargs) or "this should never be returned",
    )

    result = rag_service.generate_answer("What is the moon landing policy?", k=4)

    assert llm_calls == []
    assert result["answer"] == "I couldn't find relevant information in the uploaded documents."


def test_generate_answer_grounds_the_llm_prompt_in_retrieved_source_text(monkeypatch):
    doc = _doc(
        "Refunds are allowed within 30 days of purchase.",
        document_id="doc-9",
        filename="refund.pdf",
        page_number=2,
        chunk_index=1,
    )
    monkeypatch.setattr(rag_service, "similarity_search_with_scores", lambda **kwargs: [(doc, 0.85)])

    captured = {}

    def fake_llm(context, question):
        captured["context"] = context
        captured["question"] = question
        return "Refunds are allowed within 30 days, per the refund policy."

    monkeypatch.setattr(rag_service, "generate_llm_answer", fake_llm)

    result = rag_service.generate_answer("What is the refund window?", k=4)

    # The only source text passed to the LLM is what was actually retrieved -
    # nothing fabricated gets injected into the context.
    assert "Refunds are allowed within 30 days of purchase." in captured["context"]
    assert "refund.pdf" in captured["context"]
    assert result["sources"][0]["document"] == "refund.pdf"
    assert result["sources"][0]["page"] == 2
    assert result["answer"] == "Refunds are allowed within 30 days, per the refund policy."


def test_generate_answer_clips_context_to_configured_max_chars(monkeypatch):
    from app.config import get_settings

    get_settings().retrieval_max_context_chars = 50

    long_doc = _doc("X" * 500, document_id="doc-1", filename="big.pdf", page_number=1, chunk_index=0)
    monkeypatch.setattr(rag_service, "similarity_search_with_scores", lambda **kwargs: [(long_doc, 0.9)])

    captured = {}
    monkeypatch.setattr(
        rag_service,
        "generate_llm_answer",
        lambda context, question: captured.setdefault("context", context) or "ok",
    )

    rag_service.generate_answer("Tell me everything", k=4)

    assert len(captured["context"]) <= 50
