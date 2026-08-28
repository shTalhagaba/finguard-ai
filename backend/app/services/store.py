from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.db import db_transaction, json_dumps, json_loads


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_schema() -> None:
    with db_transaction() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              email TEXT NOT NULL UNIQUE,
              display_name TEXT NOT NULL,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
              document_id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              filename TEXT NOT NULL,
              stored_as TEXT NOT NULL,
              file_hash TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              error TEXT,
              characters_extracted INTEGER NOT NULL DEFAULT 0,
              chunks_created INTEGER NOT NULL DEFAULT 0,
              chunks_stored INTEGER NOT NULL DEFAULT 0,
              preview TEXT NOT NULL DEFAULT ''
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_user_hash
            ON documents(user_id, file_hash);

            CREATE INDEX IF NOT EXISTS idx_documents_user_updated
            ON documents(user_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS chat_sessions (
              id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              title TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              document_id TEXT,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL
            );
            """
        )


def create_user(*, email: str, display_name: str, password_hash: str) -> dict[str, Any]:
    user_id = str(uuid.uuid4())
    now = utcnow()
    with db_transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, email, display_name, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email.lower(), display_name, password_hash, now, now),
        )
    return {"id": user_id, "email": email.lower(), "display_name": display_name, "created_at": now}


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with db_transaction() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    return dict(row) if row else None


def create_chat_session(*, user_id: str, title: str | None = None) -> str:
    session_id = str(uuid.uuid4())
    now = utcnow()
    with db_transaction() as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, title, now, now),
        )
    return session_id


def append_chat_message(
    *,
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    document_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    now = utcnow()
    with db_transaction() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, user_id, role, content, document_id, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), session_id, user_id, role, content, document_id, json_dumps(metadata or {}), now),
        )
        conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ? AND user_id = ?", (now, session_id, user_id))


def list_chat_history(*, user_id: str, session_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    query = "SELECT * FROM chat_messages WHERE user_id = ?"
    params: list[Any] = [user_id]
    if session_id:
        query += " AND session_id = ?"
        params.append(session_id)
    query += " ORDER BY created_at ASC LIMIT ?"
    params.append(limit)
    with db_transaction() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    history = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json_loads(item.pop("metadata_json", "{}"), {})
        history.append(item)
    return history
