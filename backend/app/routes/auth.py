from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.auth import create_access_token, hash_password, verify_password
from app.schemas import AuthResponse, LoginRequest, RegisterRequest
from app.services.store import create_user, get_user_by_email


router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    if get_user_by_email(request.email):
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    user = create_user(
        email=request.email,
        display_name=request.display_name,
        password_hash=hash_password(request.password),
    )
    token = create_access_token(user_id=user["id"], email=user["email"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
        },
    }


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    user = get_user_by_email(request.email)
    if user is None or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token(user_id=user["id"], email=user["email"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
        },
    }
