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
uvicorn app.main:app --reload
```

The backend defaults to a local SQLite database when `DATABASE_URL` is not set, so it can run without PostgreSQL for quick development.

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

## Key API endpoints

- `GET /health`: service health and queue mode
- `GET /overview`: dashboard metrics, workflow summaries, and recent activity
- `GET /workflows`: all workflows
- `GET /workflows/{id}`: workflow detail with tasks
- `POST /workflows`: create a workflow
- `POST /workflows/{id}/tasks`: dispatch a task

## Project structure

- `backend/`: FastAPI app, SQLAlchemy models, and Celery worker
- `frontend/`: Next.js dashboard
- `docker-compose.yml`: local full-system stack

## Next improvements

- Plug real model providers into `backend/app/worker.py`
- Add authentication and per-team tenancy
- Add test coverage for API endpoints and task execution
