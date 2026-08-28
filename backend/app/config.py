import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()


class Settings(BaseModel):
    app_name: str = "FinGuard AI"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api"
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if origin.strip()
        ]
    )
    google_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY"))
    chroma_persist_directory: Path = Field(
        default_factory=lambda: Path(os.getenv("CHROMA_PERSIST_DIRECTORY", BASE_DIR / "chroma_db"))
    )
    uploads_directory: Path = Field(
        default_factory=lambda: Path(os.getenv("UPLOADS_DIRECTORY", BASE_DIR / "uploads"))
    )
    data_directory: Path = Field(default_factory=lambda: Path(os.getenv("DATA_DIRECTORY", BASE_DIR / "data")))
    database_filename: str = "finguard.sqlite3"
    auth_signing_key: str = Field(default_factory=lambda: os.getenv("AUTH_SIGNING_KEY", ""))
    allowed_hosts: list[str] = Field(
        default_factory=lambda: [
            host.strip()
            for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
            if host.strip()
        ]
    )
    password_hash_iterations: int = 390000
    access_token_ttl_minutes: int = 60 * 24
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
    if not settings.auth_signing_key:
        raise RuntimeError("AUTH_SIGNING_KEY must be set.")
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY must be set.")
    settings.chroma_persist_directory.mkdir(parents=True, exist_ok=True)
    settings.uploads_directory.mkdir(parents=True, exist_ok=True)
    settings.data_directory.mkdir(parents=True, exist_ok=True)
    return settings
