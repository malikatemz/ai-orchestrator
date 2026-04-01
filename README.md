# AI Orchestrator

AI Orchestrator is a control plane for AI workflows. It adds visibility, retry controls, queue routing, and demo-ready observability on top of multi-agent execution.

## What is included

- FastAPI backend with typed workflow, task, app-config, and ops endpoints
- Celery worker with queue lanes for `high_priority`, `default`, and `low_cost`
- PostgreSQL or SQLite persistence for workflows, tasks, and audit logs
- Next.js dashboard with public demo mode, retry actions, and a platform ops view
- Structured error handling, request IDs, Sentry hooks, and production debugging docs

## Stack

- Backend: FastAPI, Celery, SQLAlchemy, Alembic
- Frontend: Next.js, TypeScript, custom CSS
- Queue: Redis
- Database: PostgreSQL
- Infra: Docker, Docker Compose, Caddy, GitHub Actions

## Run locally

### Full stack with Docker Compose

```bash
docker-compose up --build
```

Open:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

The local compose stack runs in public demo mode and auto-seeds demo workflows.

### Backend only

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run the worker separately when you want queue-backed execution:

```bash
cd backend
celery -A app.worker.celery worker --loglevel=info -Q high_priority,default,low_cost
```

### Frontend only

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_SITE_URL` in `frontend/.env.local` when your API or domain differs from localhost.

## Production VPS deployment

1. Copy `.env.production.example` to `.env.production` and fill in real values.
2. Point your domains to the VPS:
   - app domain -> Caddy -> frontend
   - API domain -> Caddy -> backend
3. Run the deployment script:

```bash
chmod +x ops/deploy.sh
./ops/deploy.sh
```

Production uses `docker-compose.prod.yml`, Caddy for TLS, and Alembic migrations before container rollout.

## Demo flow

The dashboard now supports an explicit public demo mode:

- `GET /app-config` exposes demo/auth flags to the frontend
- `POST /seed-demo` resets seeded demo data when demo mode is enabled
- `POST /tasks/{task_id}/retry` clones and requeues failed tasks with retry lineage
- `/platform-ops` shows queue lanes, failures, and audit logs

## Key API endpoints

- `GET /health`
- `GET /app-config`
- `GET /overview`
- `GET /workflows`
- `GET /workflows/{id}`
- `GET /workflows/{id}/tasks`
- `POST /workflows`
- `POST /workflows/{id}/tasks`
- `POST /tasks/{id}/retry`
- `POST /seed-demo`
- `GET /ops/metrics`
- `GET /ops/audit-logs`

## Frontend routes

- `/`: product home plus live dashboard
- `/platform-ops`: ops metrics, audit logs, and queue-lane visibility
- `/ai-workflow-orchestration`
- `/multi-agent-orchestration`
- `/ai-operations-dashboard`
- `/ai-workflow-automation-use-cases`
- `/ai-agent-monitoring-checklist`

## Docs

- [ROADMAP.md](ROADMAP.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [DEMO.md](DEMO.md)
- [ERROR_HANDLING.md](ERROR_HANDLING.md)
- [PRODUCTION_DEBUGGING.md](PRODUCTION_DEBUGGING.md)

## Tests

### Backend

```bash
cd backend
pip install -r requirements.txt
pytest
```

### Frontend

```bash
cd frontend
npm install
npm test
npm run build
```

## Next improvements

- Add real provider integrations and agent routing heuristics
- Expand enterprise auth beyond the current token/public-demo split
- Promote the k8s scaffolds and autoscaling docs into deployable manifests when the product outgrows the VPS path
