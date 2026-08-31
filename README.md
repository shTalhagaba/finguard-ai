# FinGuard AI

FinGuard AI is a full-stack document intelligence app built with:

- Frontend: Next.js + TypeScript
- Backend: FastAPI + Python
- AI: Gemini
- Vector DB: ChromaDB

## Repo Layout

- `app/`, `package.json`, `next.config.ts`, etc. (repo root) — the Next.js frontend.
- `backend/` — the FastAPI backend (`backend/app`), its `requirements.txt`, and its own `Dockerfile`.
- `Dockerfile.frontend` (repo root) — production image for the frontend.
- `docker-compose.yml` — local orchestration of both services.

## Production Readiness

This repo includes:

- Dockerfiles for frontend and backend, with a shared `docker-compose.yml`
- Production environment examples (`.env.example` at root for the frontend, `backend/.env.example` for the backend)
- Backend health check (`GET /health`) and a centralized unhandled-exception handler
- Structured request logging, CORS, and trusted-host configuration
- Secrets loaded only from gitignored `.env` files / platform secret stores, never hardcoded
- GitHub Actions CI/CD workflow (lint, build, settings validation, Docker build checks)
- Azure deployment architecture guidance

## ⚠ Security Notice

An earlier commit in this repository's history committed `backend/.env` with a real-looking `GOOGLE_API_KEY`, and it reached `origin/main`. That file has been removed from git tracking (`git rm --cached`), but **it still exists in git history and on the remote until history is rewritten**. Treat that key as compromised:

1. Rotate/revoke it immediately in Google AI Studio / Google Cloud Console.
2. Put the new key only in a local, gitignored `backend/.env` — never commit it.
3. If you control the remote and no one else has pulled the affected commits, consider purging it from history (`git filter-repo` or BFG) and force-pushing. This rewrites shared history, so coordinate with any collaborators first.

Previously-committed backend runtime files (`backend/chroma_db/`, `backend/uploads/`) — persisted vector DB data and uploaded user PDFs — have also been untracked; they don't belong in source control.

## Environment Variables

Do not commit secrets to the repo. Use secret storage in your platform or local `.env` files derived from the example files.

### Backend

Copy [`backend/.env.example`](backend/.env.example) to `backend/.env` and set:

- `AUTH_SIGNING_KEY` — long random secret used to sign auth tokens
- `GOOGLE_API_KEY` — Gemini API key (server-side only, never exposed to the frontend)
- `CORS_ORIGINS` — comma-separated list of allowed frontend origins
- `ALLOWED_HOSTS` — comma-separated list of allowed `Host` headers
- `DATA_DIRECTORY`, `UPLOADS_DIRECTORY`, `CHROMA_PERSIST_DIRECTORY` — persistence paths

`backend/.env` is gitignored. `docker-compose.yml` loads secrets from this file, so it must exist locally before running `docker compose up`.

### Frontend

Copy [`.env.example`](.env.example) (repo root) to `.env.local` for local development and set:

- `NEXT_PUBLIC_API_URL` — base URL of the backend API

For Docker builds this is instead passed as the `NEXT_PUBLIC_API_URL` build arg (see `docker-compose.yml`), since Next.js inlines `NEXT_PUBLIC_*` vars at build time.

## Local Development

### With Docker

```bash
cp backend/.env.example backend/.env   # fill in real secrets first
docker compose up --build
```

This starts:

- Frontend on `http://localhost:3000`
- Backend on `http://localhost:8000`

### Without Docker

Backend:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real secrets first
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend (from repo root):

```bash
cp .env.example .env.local
npm install
npm run build
npm run start
```

## Deployment Architecture

Recommended Azure layout:

- Azure Front Door or Azure Application Gateway for TLS termination and routing
- Azure Container Registry for container images
- Azure Container Apps or Azure App Service for the frontend and backend containers
- Azure Key Vault for `AUTH_SIGNING_KEY`, `GOOGLE_API_KEY`, and other secrets — injected as container app secrets/env vars, never baked into images
- Azure Files or a managed persistent volume for backend data and Chroma persistence
- Azure Monitor and Application Insights for logs, metrics, and alerts

### Runtime Flow

1. Browser hits the Next.js frontend.
2. Frontend calls the FastAPI backend through `NEXT_PUBLIC_API_URL`.
3. Backend authenticates requests, writes document metadata to SQLite, and persists embeddings in ChromaDB.
4. Gemini is called only from the backend using the server-side API key.

### Security Notes

- Keep `GOOGLE_API_KEY` server-side only.
- Keep `AUTH_SIGNING_KEY` in a secret store (Azure Key Vault in production).
- Restrict `CORS_ORIGINS` to the real frontend origin.
- Restrict `ALLOWED_HOSTS` to the actual deployment hostnames.
- Never commit `.env` files — only `.env.example` files with placeholder values belong in git.

## CI/CD

The workflow in [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) runs on every push/PR to `main`:

- Frontend: `npm ci`, lint, production build
- Backend: install deps, bytecode-compile, validate settings load with CI placeholder env vars
- Docker: build both images (frontend via `Dockerfile.frontend`, backend via `backend/Dockerfile`) without pushing

For Azure deployment, extend the `docker` job to:

- Log in to Azure Container Registry
- Push the built images with a commit-SHA tag
- Deploy the new image tags to Azure Container Apps or App Service (e.g. `az containerapp update`)

## Health Check

The backend exposes:

- `GET /health` — returns service status and environment; used by the Docker healthcheck and should back any load balancer / container app probe.

## Monitoring

Start with:

- Container logs shipped to Azure Monitor / Log Analytics
- Application Insights alerts on 5xx spikes and elevated latency
- Health probe alerts for failed `/health` checks
- Basic uptime checks from a synthetic monitor (e.g. Azure Monitor availability tests)

## Notes

- Do not hardcode secrets into Dockerfiles, compose files, or source code — see the Security Notice above.
- `.dockerignore` excludes `backend/venv`, `backend/chroma_db`, `backend/uploads`, `backend/data`, and all `.env*` files (except `.env.example`) from the Docker build context.
