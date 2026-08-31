from __future__ import annotations


def _post_files(client, headers, files):
    return client.post("/api/upload", files=files, headers=headers)


# ---------------------------------------------------------------------------
# PDF upload (happy path)
# ---------------------------------------------------------------------------


def test_upload_pdf_success(client, auth_headers, sample_pdf_bytes, monkeypatch):
    import app.routes.upload as upload_route

    monkeypatch.setattr(upload_route, "add_document_chunks", lambda **kwargs: len(kwargs["chunks"]))

    response = _post_files(
        client,
        auth_headers,
        files=[("files", ("kyc-policy.pdf", sample_pdf_bytes, "application/pdf"))],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["failures"] == []
    document = body["documents"][0]
    assert document["filename"] == "kyc-policy.pdf"
    assert document["status"] == "completed"
    assert document["chunks_created"] > 0
    assert document["chunks_stored"] == document["chunks_created"]
    assert document["characters_extracted"] > 0


def test_upload_requires_authentication(client, sample_pdf_bytes):
    response = _post_files(
        client,
        headers={},
        files=[("files", ("policy.pdf", sample_pdf_bytes, "application/pdf"))],
    )
    assert response.status_code == 401


def test_upload_deduplicates_identical_files(client, auth_headers, sample_pdf_bytes, monkeypatch):
    import app.routes.upload as upload_route

    monkeypatch.setattr(upload_route, "add_document_chunks", lambda **kwargs: len(kwargs["chunks"]))

    first = _post_files(client, auth_headers, files=[("files", ("policy.pdf", sample_pdf_bytes, "application/pdf"))])
    assert first.json()["documents"][0]["status"] == "completed"

    second = _post_files(client, auth_headers, files=[("files", ("policy.pdf", sample_pdf_bytes, "application/pdf"))])
    assert second.json()["documents"][0]["status"] == "duplicate"


# ---------------------------------------------------------------------------
# Invalid files
# ---------------------------------------------------------------------------


def test_upload_rejects_non_pdf_extension(client, auth_headers):
    response = _post_files(
        client,
        auth_headers,
        files=[("files", ("notes.txt", b"hello world", "text/plain"))],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == []
    assert body["failures"][0]["detail"] == "Only PDF files are allowed."


def test_upload_rejects_corrupted_pdf(client, auth_headers):
    response = _post_files(
        client,
        auth_headers,
        files=[("files", ("broken.pdf", b"%PDF-1.4 not a real pdf body", "application/pdf"))],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == []
    failure = body["failures"][0]
    assert "document_id" in failure
    assert "Failed to read PDF" in failure["detail"]


def test_upload_rejects_oversized_file(client, auth_headers, sample_pdf_bytes):
    from app.config import get_settings

    get_settings().max_upload_size_mb = 0

    response = _post_files(
        client,
        auth_headers,
        files=[("files", ("policy.pdf", sample_pdf_bytes, "application/pdf"))],
    )

    body = response.json()
    assert body["documents"] == []
    assert "too large" in body["failures"][0]["detail"].lower()


def test_upload_requires_at_least_one_file(client, auth_headers):
    response = client.post("/api/upload", headers=auth_headers)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Empty documents
# ---------------------------------------------------------------------------


def test_upload_rejects_empty_file(client, auth_headers):
    response = _post_files(
        client,
        auth_headers,
        files=[("files", ("empty.pdf", b"", "application/pdf"))],
    )

    body = response.json()
    assert body["documents"] == []
    assert body["failures"][0]["detail"] == "Uploaded file is empty."


def test_upload_rejects_pdf_with_no_extractable_text(client, auth_headers, blank_pdf_bytes):
    response = _post_files(
        client,
        auth_headers,
        files=[("files", ("blank.pdf", blank_pdf_bytes, "application/pdf"))],
    )

    body = response.json()
    assert body["documents"] == []
    failure = body["failures"][0]
    assert failure["detail"] == "Could not extract text from this PDF."
    assert "document_id" in failure


# ---------------------------------------------------------------------------
# Document retrieval
# ---------------------------------------------------------------------------


def test_get_documents_empty_for_new_user(client, auth_headers):
    response = client.get("/api/documents", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"documents": []}


def test_get_documents_requires_authentication(client):
    response = client.get("/api/documents")
    assert response.status_code == 401


def test_get_documents_after_successful_upload(client, auth_headers, sample_pdf_bytes, monkeypatch):
    import app.routes.upload as upload_route

    monkeypatch.setattr(upload_route, "add_document_chunks", lambda **kwargs: len(kwargs["chunks"]))

    _post_files(client, auth_headers, files=[("files", ("kyc-policy.pdf", sample_pdf_bytes, "application/pdf"))])

    response = client.get("/api/documents", headers=auth_headers)
    documents = response.json()["documents"]
    assert len(documents) == 1
    assert documents[0]["filename"] == "kyc-policy.pdf"
    assert documents[0]["status"] == "completed"


def test_documents_are_scoped_to_the_uploading_user(client, register_user, sample_pdf_bytes, monkeypatch):
    import app.routes.upload as upload_route

    monkeypatch.setattr(upload_route, "add_document_chunks", lambda **kwargs: len(kwargs["chunks"]))

    owner = register_user(email="owner@example.com")
    other = register_user(email="other@example.com")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    _post_files(client, owner_headers, files=[("files", ("policy.pdf", sample_pdf_bytes, "application/pdf"))])

    assert client.get("/api/documents", headers=owner_headers).json()["documents"]
    assert client.get("/api/documents", headers=other_headers).json()["documents"] == []
