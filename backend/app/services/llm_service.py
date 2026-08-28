from functools import lru_cache

from fastapi import HTTPException
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings


@lru_cache(maxsize=1)
def get_llm() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    if not settings.google_api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY is not configured.")

    return ChatGoogleGenerativeAI(
        model=settings.gemini_chat_model,
        google_api_key=settings.google_api_key,
        temperature=0.2,
    )


def build_prompt(context: str, question: str) -> str:
    return f"""You are FinGuard AI, a production-oriented fintech document assistant.

Use only the provided context to answer the question.
If the context does not contain enough information, say that clearly.
Do not invent facts or rely on outside knowledge.
Keep the answer concise, professional, and useful.
When sources include page numbers or relevance details, use them if they help answer the question.

CONTEXT:
{context}

QUESTION:
{question}
"""


def generate_answer(context: str, question: str) -> str:
    response = get_llm().invoke(build_prompt(context, question))
    return response.content
