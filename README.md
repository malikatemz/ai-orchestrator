# AI Orchestrator

An orchestration control plane for AI workflows with a FastAPI backend, Celery worker, Redis queue, PostgreSQL database, and a Next.js dashboard for live oversight.

## What is included

- Typed workflow and task APIs with validation
- Overview and health endpoints for system monitoring
- Seeded demo workflows so the dashboard is useful on first boot
- Task execution lifecycle with inline fallback when Celery is unavailable
- A dashboard for workflow creation, queue monitoring, and execution detail

## Run with Docker

1. Install Docker Desktop.
2. From the project root, run:

```bash
docker-compose up --build
```

3. Open the apps:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Run locally

### Backend API

```bash
cd backend
pip install -r requirements.txt
cp ../.env .env
uvicorn app.main:app --reload
```

The backend defaults to a local SQLite database when `DATABASE_URL` is not set, so it can run without PostgreSQL for quick development.

#### Security
- Requires bearer token auth:
  `Authorization: Bearer <API_TOKEN>`
- Default token is set in `.env` as `API_TOKEN`.
- Basic rate limit applied: 60 requests per minute per client.

### Worker

```bash
cd backend
celery -A app.worker worker --loglevel=info
```

If Redis or Celery is not available, task creation still works because the API falls back to inline execution.

### Frontend

```bash
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` if your API is not running on `http://localhost:8000`.
Set `NEXT_PUBLIC_SITE_URL` to your real production domain before deploying so canonicals, JSON-LD, `robots.txt`, and `sitemap.xml` do not reference localhost.

## Test suite

### Backend tests

```bash
cd backend
pytest
```

### Frontend tests

```bash
cd frontend
npm install
npm test
```

## Key API endpoints

- `GET /health`: service health and queue mode
- `GET /overview`: dashboard metrics, workflow summaries, and recent activity
- `GET /workflows`: all workflows
- `GET /workflows/{id}`: workflow detail with tasks
- `POST /workflows`: create a workflow
- `POST /workflows/{id}/tasks`: dispatch a task

## Frontend routes

- `/`: product home plus live dashboard
- `/ai-workflow-orchestration`: landing page for workflow orchestration intent
- `/multi-agent-orchestration`: landing page for multi-agent coordination intent
- `/ai-operations-dashboard`: landing page for monitoring and dashboard intent
- `/ai-workflow-automation-use-cases`: solution-focused page with practical automation examples
- `/ai-agent-monitoring-checklist`: tactical page for production monitoring and reliability reviews

## Project structure

- `backend/`: FastAPI app, SQLAlchemy models, and Celery worker
- `frontend/`: Next.js dashboard
- `docker-compose.yml`: local full-system stack
- `ERROR_HANDLING.md`: error taxonomy, retries, observability, and alert thresholds
- `PRODUCTION_DEBUGGING.md`: 10-step debugging runbook and environment diff checklist

## Next improvements

- Plug real model providers into `backend/app/worker.py`
- Add authentication and per-team tenancy
- Add test coverage for API endpoints and task execution
