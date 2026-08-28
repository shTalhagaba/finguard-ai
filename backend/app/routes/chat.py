from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.services.rag_service import generate_answer


router = APIRouter(prefix="/api", tags=["Chat"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=10)
    document_id: str | None = None


@router.post("/chat")
async def chat_with_documents(request: ChatRequest):
    try:
        result = generate_answer(
            query=request.question,
            k=request.top_k,
            document_id=request.document_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat request failed: {exc}") from exc
