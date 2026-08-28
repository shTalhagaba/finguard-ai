from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.routes import auth, chat, upload
from app.services.store import init_schema


settings = get_settings()
logger = logging.getLogger("finguard.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        logger.info(
            "%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response


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
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled application error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


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
        "environment": settings.environment,
    }
