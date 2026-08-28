from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import auth, chat, upload
from app.services.store import init_schema


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.chroma_persist_directory.mkdir(parents=True, exist_ok=True)
    settings.uploads_directory.mkdir(parents=True, exist_ok=True)
    settings.data_directory.mkdir(parents=True, exist_ok=True)
    init_schema()
    yield


app = FastAPI(
    title=settings.app_name,
    description="AI-powered Fintech RAG Assistant",
    version=settings.app_version,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(auth.router)


@app.get("/")
async def root():
    return {
        "message": "FinGuard AI API is running",
        "version": settings.app_version,
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.app_name,
    }
