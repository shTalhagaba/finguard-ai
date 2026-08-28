from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import upload, chat


app = FastAPI(
    title="FinGuard AI",
    description="AI-powered Fintech RAG Assistant",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(upload.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    return {
        "message": "FinGuard AI API is running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy"
    }