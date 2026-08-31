from __future__ import annotations


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------


def test_chat_requires_authentication(client):
    response = client.post("/api/chat", json={"question": "What is KYC?"})
    assert response.status_code == 401


def test_chat_rejects_empty_question(client, auth_headers):
    response = client.post("/api/chat", json={"question": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_chat_returns_answer_with_sources_and_session_id(client, auth_headers, monkeypatch):
    import app.routes.chat as chat_route

    def fake_generate_answer(**kwargs):
        assert kwargs["query"] == "What is KYC?"
        return {
            "answer": "KYC requires verifying customer identity documents.",
            "sources": [
                {
                    "document": "kyc-policy.pdf",
                    "page": 1,
                    "chunk": {"index": 0},
                    "excerpt": "Verify customer identity before onboarding.",
                    "document_id": "doc-1",
                    "relevance_score": 0.92,
                }
            ],
            "contextualized_query": kwargs["query"],
            "task": "kyc_policy_qa",
        }

    monkeypatch.setattr(chat_route, "generate_answer", fake_generate_answer)

    response = client.post("/api/chat", json={"question": "What is KYC?"}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "KYC requires verifying customer identity documents."
    assert body["sources"][0]["document"] == "kyc-policy.pdf"
    assert body["sources"][0]["page"] == 1
    assert body["session_id"]


def test_chat_reuses_supplied_session_id_across_turns(client, auth_headers, monkeypatch):
    import app.routes.chat as chat_route

    monkeypatch.setattr(
        chat_route,
        "generate_answer",
        lambda **kwargs: {"answer": "ok", "sources": [], "contextualized_query": kwargs["query"]},
    )

    first = client.post("/api/chat", json={"question": "What is KYC?"}, headers=auth_headers)
    session_id = first.json()["session_id"]
    assert session_id

    second = client.post(
        "/api/chat",
        json={"question": "And AML?", "session_id": session_id},
        headers=auth_headers,
    )

    assert second.json()["session_id"] == session_id


def test_chat_wraps_unexpected_errors_as_500(client, auth_headers, monkeypatch):
    import app.routes.chat as chat_route

    def boom(**kwargs):
        raise RuntimeError("vector store unavailable")

    monkeypatch.setattr(chat_route, "generate_answer", boom)

    response = client.post("/api/chat", json={"question": "What is KYC?"}, headers=auth_headers)

    assert response.status_code == 500
    assert "vector store unavailable" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Empty documents / unsupported questions (full request path)
# ---------------------------------------------------------------------------


def test_chat_with_no_uploaded_documents_returns_graceful_fallback(client, auth_headers, monkeypatch):
    import app.services.rag_service as rag_service

    monkeypatch.setattr(rag_service, "similarity_search_with_scores", lambda **kwargs: [])
    llm_calls = []
    monkeypatch.setattr(rag_service, "generate_llm_answer", lambda **kwargs: llm_calls.append(kwargs))

    response = client.post(
        "/api/chat", json={"question": "What are the KYC requirements?"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "I couldn't find relevant information in the uploaded documents."
    assert body["sources"] == []
    assert llm_calls == []


def test_chat_handles_unsupported_question_via_route(client, auth_headers, monkeypatch):
    import app.routes.chat as chat_route

    monkeypatch.setattr(
        chat_route,
        "generate_answer",
        lambda **kwargs: {
            "answer": "I couldn't find relevant information in the uploaded documents.",
            "sources": [],
            "contextualized_query": kwargs["query"],
        },
    )

    response = client.post(
        "/api/chat", json={"question": "What's the weather like on Mars?"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert "couldn't find" in body["answer"]
