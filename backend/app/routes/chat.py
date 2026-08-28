from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.services.rag_service import generate_answer
from app.services.store import append_chat_message, create_chat_session


router = APIRouter(prefix="/api", tags=["Chat"])


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=10)
    document_id: str | None = None
    chat_history: list[ChatTurn] = Field(default_factory=list)
    session_id: str | None = None


@router.post("/chat")
async def chat_with_documents(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        session_id = request.session_id or create_chat_session(user_id=current_user["id"], title=request.question[:80])
        append_chat_message(
            session_id=session_id,
            user_id=current_user["id"],
            role="user",
            content=request.question,
            document_id=request.document_id,
        )
        result = generate_answer(
            query=request.question,
            k=request.top_k,
            document_id=request.document_id,
            chat_history=[turn.model_dump() for turn in request.chat_history],
            user_id=current_user["id"],
        )
        append_chat_message(
            session_id=session_id,
            user_id=current_user["id"],
            role="assistant",
            content=result.get("answer", ""),
            document_id=request.document_id,
            metadata={"sources": result.get("sources", [])},
        )
        result["session_id"] = session_id
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat request failed: {exc}") from exc
