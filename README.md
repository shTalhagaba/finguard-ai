# FinGuard AI

FinGuard AI is a full-stack document intelligence app built with:

- Frontend: Next.js + TypeScript
- Backend: FastAPI + Python
- AI: Gemini
- Vector DB: ChromaDB

## Production Readiness

This repo now includes:

- Dockerfiles for frontend and backend
- `docker-compose.yml` for local orchestration
- Production environment examples
- Backend health check and centralized error handling
- Logging and CORS configuration
- Secure secret handling through environment variables
- GitHub Actions CI/CD workflow
- Azure deployment architecture guidance

## Environment Variables

Do not commit secrets to the repo. Use secret storage in your platform or local `.env` files derived from the example files.

### Backend

Copy [`backend/.env.example`](backend/.env.example) and set:

- `AUTH_SIGNING_KEY`
- `GOOGLE_API_KEY`
- `CORS_ORIGINS`
- `ALLOWED_HOSTS`
- `DATA_DIRECTORY`
- `UPLOADS_DIRECTORY`
- `CHROMA_PERSIST_DIRECTORY`

### Frontend

Copy [`frontend/.env.example`](frontend/.env.example) and set:

- `NEXT_PUBLIC_API_URL`

## Local Development

### With Docker

```bash
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
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run build
npm run start
```

## Deployment Architecture

Recommended Azure layout:

- Azure Front Door or Azure Application Gateway for TLS termination and routing
- Azure Container Registry for container images
- Azure Container Apps or Azure App Service for the frontend and backend containers
- Azure Key Vault for `AUTH_SIGNING_KEY`, `GOOGLE_API_KEY`, and other secrets
- Azure Files or managed persistent volume for backend data and Chroma persistence
- Azure Monitor and Application Insights for logs, metrics, and alerts

### Runtime Flow

1. Browser hits the Next.js frontend.
2. Frontend calls the FastAPI backend through `NEXT_PUBLIC_API_URL`.
3. Backend authenticates requests, writes document metadata to SQLite, and persists embeddings in ChromaDB.
4. Gemini is called only from the backend using the server-side API key.

### Security Notes

- Keep `GOOGLE_API_KEY` server-side only.
- Keep `AUTH_SIGNING_KEY` in a secret store.
- Restrict `CORS_ORIGINS` to the real frontend origin.
- Restrict `ALLOWED_HOSTS` to the actual deployment hostnames.

## CI/CD

The workflow in [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) runs:

- Frontend lint and production build
- Backend bytecode compilation and settings validation
- Docker image build checks

For Azure deployment, extend the workflow to:

- Build images
- Push to Azure Container Registry
- Deploy the new image tags to Azure Container Apps or App Service

## Health Check

The backend exposes:

- `GET /health`

Use it for container probes and load balancer health checks.

## Monitoring

Start with:

- Container logs shipped to Azure Monitor
- Application Insights or Log Analytics alerts on 5xx spikes
- Health probe alerts for failed `/health` checks
- Basic uptime checks from a synthetic monitor

## Notes

- The repo is structured with a dedicated `frontend/` Next.js app and a dedicated `backend/` FastAPI app.
- Do not hardcode secrets into Dockerfiles, compose files, or source code.
