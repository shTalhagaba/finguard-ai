import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()


class Settings(BaseModel):
    app_name: str = "FinGuard AI"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    google_api_key: str | None = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY"))
    chroma_persist_directory: Path = BASE_DIR / "chroma_db"
    uploads_directory: Path = BASE_DIR / "uploads"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    gemini_chat_model: str = "gemini-2.5-flash"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    chunk_min_size: int = 200
    retrieval_initial_k: int = 12
    retrieval_max_context_chunks: int = 6
    retrieval_max_context_chars: int = 12000
    retrieval_min_relevance_score: float = 0.2
    retrieval_max_results: int = 10
    max_upload_size_mb: int = 20


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.chroma_persist_directory.mkdir(parents=True, exist_ok=True)
    settings.uploads_directory.mkdir(parents=True, exist_ok=True)
    return settings
