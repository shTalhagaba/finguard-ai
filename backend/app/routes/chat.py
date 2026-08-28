from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.rag_service import generate_answer


router = APIRouter(
    prefix="/api",
    tags=["Chat"]
)


class ChatRequest(BaseModel):
    question: str


@router.post("/chat")
async def chat_with_documents(request: ChatRequest):

    try:
        result = generate_answer(
            query=request.question
        )

        return result

    except Exception as e:
        print(f"CHAT ERROR: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )