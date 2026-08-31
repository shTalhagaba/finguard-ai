# FinGuard AI

An AI-powered fintech policy assistant. Users upload policy documents (PDFs), and a
retrieval-augmented generation (RAG) pipeline answers questions grounded in that
content, scoped per-user with authentication.

- **Frontend**: [Next.js 16](https://nextjs.org) (App Router), React 19, Tailwind CSS 4
- **Backend**: FastAPI, ChromaDB (vector store), Google Gemini (chat + embeddings)
- **Auth**: Token-based, multi-user with per-user document ownership scoping

## Project layout

```
.
├── app/            # Next.js App Router pages
├── backend/
│   ├── app/
│   │   ├── main.py       # FastAPI app entrypoint
│   │   ├── auth.py       # Password hashing / token issuance
│   │   ├── config.py     # Settings (env-driven)
│   │   ├── routes/       # /api/auth, /api/upload, /api/chat
│   │   └── services/     # Document processing, vector store, RAG, LLM calls
│   └── tests/
├── tests/          # Frontend tests (Vitest + Testing Library)
└── Dockerfile      # Production frontend build
```

## Getting started

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in GOOGLE_API_KEY and AUTH_SIGNING_KEY
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`.

Required environment variables (see `backend/.env.example`):

| Variable | Description |
| --- | --- |
| `GOOGLE_API_KEY` | Google Gemini API key, used for embeddings and chat completion |
| `AUTH_SIGNING_KEY` | Secret used to sign access tokens — set a real value outside local dev |

### Frontend

```bash
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL if the backend isn't on :8000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Tests

```bash
# Frontend
npm run test

# Backend
cd backend && venv/bin/pytest
```

## Docker

The `Dockerfile` builds a production frontend image:

```bash
docker build --build-arg NEXT_PUBLIC_API_URL=https://your-api-host -t finguard-frontend .
docker run -p 3000:3000 finguard-frontend
```

The backend is not containerized yet; run it directly with `uvicorn` as above.

## API overview

| Route | Description |
| --- | --- |
| `POST /api/auth/register` | Create an account |
| `POST /api/auth/login` | Exchange credentials for an access token |
| `POST /api/upload` | Upload a PDF, chunk it, and index it in the vector store |
| `POST /api/chat` | Ask a question; retrieves relevant chunks and generates a grounded answer |

Chat and upload routes require a bearer token from `/api/auth/login`; documents and
chat sessions are scoped to the authenticated user.
