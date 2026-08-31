from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.db import db_transaction

bearer_scheme = HTTPBearer(auto_error=False)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    settings = get_settings()
    salt = salt or secrets.token_bytes(16)
    rounds = settings.password_hash_iterations
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${_b64url_encode(salt)}${_b64url_encode(derived)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds_text, salt_text, hash_text = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_text)
        salt = _b64url_decode(salt_text)
        expected = _b64url_decode(hash_text)
    except Exception:
        return False
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(derived, expected)


def _sign(payload_text: str) -> str:
    settings = get_settings()
    digest = hmac.new(
        settings.auth_signing_key.encode("utf-8"),
        payload_text.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def create_access_token(*, user_id: str, email: str) -> str:
    settings = get_settings()
    if not settings.auth_signing_key:
        raise HTTPException(status_code=500, detail="AUTH_SIGNING_KEY is not configured.")
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.access_token_ttl_minutes * 60,
    }
    payload_text = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{payload_text}.{_sign(payload_text)}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload_text, signature = token.split(".", 1)
        if not hmac.compare_digest(_sign(payload_text), signature):
            raise ValueError("bad signature")
        payload = json.loads(_b64url_decode(payload_text).decode("utf-8"))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication required.")

    token_data = decode_access_token(credentials.credentials)
    user_id = token_data.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    with db_transaction() as conn:
        user = conn.execute(
            "SELECT id, email, display_name, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return dict(user)
