# Local Development Setup Guide

Complete guide for running AI Orchestration Platform locally for development.

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15
- Redis 7
- Docker & Docker Compose (optional, for containerized local development)

## Option A: Docker Compose (Single Command)

### Start All Services

```bash
cd /path/to/orchestrator

docker-compose up -d
```

This spawns:
- PostgreSQL (port 5432)
- Redis (port 6379)
- API (port 8000)
- Worker (port 5555 Flower monitoring)
- Frontend (port 3000)

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f worker
```

### Stop Services

```bash
docker-compose down
```

### Access Points

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Frontend: http://localhost:3000
- Worker Monitor: http://localhost:5555

---

## Option B: Local Native Setup

### 1. Database Setup

Start PostgreSQL:

```bash
# macOS with Homebrew
brew services start postgresql@15

# Linux
sudo systemctl start postgresql

# Or Docker
docker run -d \
  --name postgres \
  -e POSTGRES_USER=orchestrator \
  -e POSTGRES_PASSWORD=dev123 \
  -e POSTGRES_DB=orchestrator \
  -p 5432:5432 \
  postgres:15
```

Create database & user:

```bash
psql -U postgres

CREATE USER orchestrator WITH PASSWORD 'dev123';
CREATE DATABASE orchestrator OWNER orchestrator;
GRANT ALL PRIVILEGES ON DATABASE orchestrator TO orchestrator;
\q
```

### 2. Redis Setup

Start Redis:

```bash
# macOS with Homebrew
brew services start redis

# Linux
sudo systemctl start redis-server

# Or Docker
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:7
```

### 3. Backend Setup

Create virtual environment:

```bash
cd backend

python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env` file:

```bash
cat > .env << EOF
# Database
DATABASE_URL=postgresql://orchestrator:dev123@localhost:5432/orchestrator

# Redis
REDIS_URL=redis://localhost:6379

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...

# Stripe
STRIPE_SECRET_KEY=sk_test_...

# OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

# JWT
JWT_SECRET_KEY=$(openssl rand -hex 32)

# App
APP_MODE=dev
LOG_LEVEL=DEBUG
EOF
```

Run migrations:

```bash
alembic upgrade head
```

Start API server:

```bash
uvicorn app.main:app --reload --port 8000
```

API runs at http://localhost:8000

### 4. Worker Setup

In another terminal:

```bash
cd backend

source venv/bin/activate

celery -A app.worker worker --loglevel=info
```

Monitor with Flower:

```bash
celery -A app.worker flower --port=5555
```

Access Flower at http://localhost:5555

### 5. Frontend Setup

```bash
cd frontend

# Create .env.local
cat > .env.local << EOF
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_SITE_URL=http://localhost:3000
EOF

npm install
npm run dev
```

Frontend runs at http://localhost:3000

---

## Development Workflow

### API Development

Update `backend/app/routes_*.py` or `backend/app/agents/*` files.

Uvicorn with `--reload` automatically restarts on file changes.

Test endpoints:

```bash
# Health check
curl http://localhost:8000/health

# Create task (requires auth token)
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"summarize","input":"..."}'
```

### Worker Development

Celery doesn't hot-reload. Restart the worker:

```bash
# Stop current worker (Ctrl+C)
# Modify code
# Restart
celery -A app.worker worker --loglevel=info
```

Monitor task execution in Flower or logs.

### Frontend Development

Next.js with fast refresh automatically reloads on file changes.

Update `frontend/pages/*` or `frontend/components/*`.

### Database Changes

After modifying `backend/app/models.py`:

```bash
cd backend

# Auto-generate migration
alembic revision --autogenerate -m "Add new column"

# Review migration in migrations/versions/
# Apply
alembic upgrade head
```

### Testing

#### Backend Tests

```bash
cd backend

pytest
pytest -v tests/test_agents.py  # Specific test file
pytest -k "test_scoring"         # Specific test
pytest --cov=app                 # Coverage
```

#### Frontend Tests

```bash
cd frontend

npm test
npm test -- --coverage
```

---

## Common Development Tasks

### Reset Database

```bash
cd backend

# Drop and recreate
alembic downgrade base
alembic upgrade head

# Or directly
psql -U orchestrator -d orchestrator < /dev/null
psql orchestrator -U orchestrator -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
alembic upgrade head
```

### Clear Redis Cache

```bash
redis-cli

FLUSHDB  # Current DB
FLUSHALL # All DBs
```

### View Database

```bash
psql -U orchestrator -d orchestrator

\dt           # List tables
\d users      # Describe table
SELECT * FROM users;
```

### Admin User for Testing

Create a test user (in API):

```bash
from backend.app.models import User, Organization, UserRole
from backend.app.database import SessionLocal

db = SessionLocal()

org = Organization(
    id="org-test",
    name="Test Org",
    subscription_status="active"
)
user = User(
    id="user-test",
    email="test@example.com",
    org_id="org-test",
    role=UserRole.OWNER
)

db.add(org)
db.add(user)
db.commit()
```

Then login via OAuth or get JWT:

```bash
curl -X POST http://localhost:8000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"..."}' \
```

### Testing OAuth Flows Locally

Google OAuth requires redirect URI registered. For local dev:

1. Add `http://localhost:3000/auth/callback` to Google Console redirect URIs
2. Frontend redirects to `/auth/google`
3. API redirects to Google OAuth URL
4. User authorizes
5. Google redirects to API callback, which redirects to frontend with JWT

Or use a tunnel service for local-to-internet exposure:

```bash
ngrok http 3000
# Tunnel: https://abcd1234.ngrok.io

# Register with Auth provider:
# https://abcd1234.ngrok.io/auth/google/callback

# Access frontend via ngrok URL (not localhost)
```

### Seed Test Data

Create `backend/scripts/seed.py`:

```python
from backend.app.database import SessionLocal
from backend.app.models import Organization, User, Task, UserRole

db = SessionLocal()

# Organization
org = Organization(id="org-seed", name="Seed Org", subscription_status="active")
db.add(org)

# User
user = User(
    id="user-seed",
    email="seed@example.com",
    org_id="org-seed",
    role=UserRole.OWNER
)
db.add(user)

# Tasks
for i in range(5):
    task = Task(
        id=f"task-seed-{i}",
        org_id="org-seed",
        task_type="summarize",
        input_data={"text": f"Sample text {i}"},
        status="pending"
    )
    db.add(task)

db.commit()
print("Seeded test data")
```

Run:

```bash
cd backend
python scripts/seed.py
```

### View Agent Scoring in Action

Monitor provider selection:

```bash
# Terminal 1: Make a request
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"summarize","input":"..."}'

# Terminal 2: Watch worker logs
celery -A app.worker worker --loglevel=debug | grep "provider_selection\|score"

# Or check FlowerUI at http://localhost:5555
```

---

## Debugging

### Backend Debugging with pdb

Add breakpoint in code:

```python
from app.agents.router import select_agent

def my_function():
    breakpoint()  # Will pause here
    result = select_agent(db, "summarize")
    return result
```

Run:

```bash
# With Uvicorn (single-threaded)
uvicorn app.main:app --reload --port 8000

# Or with Python directly
python -m debugpy --listen 127.0.0.1:5678 -m uvicorn app.main:app --reload
```

Debugger will pause at breakpoint. Commands: `n` (next), `s` (step), `c` (continue), `l` (list), `p var` (print).

### Remote Debugging with VS Code

Install extension: Python

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--port", "8000"],
      "jinja": true,
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

Click "Run and Debug" or F5.

### Frontend Debugging

Browser DevTools (F12):
- Network tab: Monitor API calls
- Application tab: View localStorage (JWT), cookies
- Console: Errors and logs
- React DevTools extension: Component tree and state

---

## Observability

### Health Checks

All services expose health endpoints:

```bash
# API
curl http://localhost:8000/health

# Output
{
  "status": "ok",
  "database": "connected",
  "redis": "connected",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Logs

Config logging in `backend/app/config.py`:

```python
LOG_LEVEL = "DEBUG"  # In dev
SENTRY_DSN = None    # In dev (optional)
```

Structured logging via `structlog`:

```python
import structlog
logger = structlog.get_logger()

logger.info("task_executed", task_id="123", provider="openai", duration_ms=1234)
```

View logs:

```bash
# API
docker logs -f orchestrator-api

# Worker
celery -A app.worker worker --loglevel=debug
```

### Metrics

Prometheus metrics exposed at `/metrics`:

```bash
curl http://localhost:8000/metrics
```

Sample output:

```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="POST",endpoint="/tasks"} 42.0

# HELP task_execution_duration_seconds Task execution duration
# TYPE task_execution_duration_seconds histogram
task_execution_duration_seconds_bucket{provider="openai",le="1.0"} 10.0
```

---

## Useful Commands

```bash
# Backend terminal
cd backend && source venv/bin/activate

# Start API (http://localhost:8000)
uvicorn app.main:app --reload

# Start worker (processes tasks)
celery -A app.worker worker --loglevel=info

# Run tests
pytest -v

# Create migration
alembic revision --autogenerate -m "Description"
alembic upgrade head

# Check syntax
python -m py_compile app/main.py

# Type checking
mypy app/

# Formatting
black app/
isort app/

# Linting
flake8 app/
```

```bash
# Frontend terminal
cd frontend

# Install dependencies
npm install

# Dev server (http://localhost:3000)
npm run dev

# Build for production
npm run build
npm start

# Test
npm test

# Lint
npm run lint

# Type check (TypeScript)
npm run type-check

# Format
npm run format
```

---

## Troubleshooting

### API won't start: "Database connection refused"

```bash
# Check PostgreSQL is running
psql -U orchestrator -d orchestrator -c "SELECT 1"

# If not:
brew services start postgresql@15
# or
docker start postgres
```

### Tasks not executing: "Worker not processing"

```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Check worker is connected to Redis
celery -A app.worker worker --loglevel=debug | grep "connected to"

# Check queue has tasks
redis-cli LLEN celery
```

### Frontend OAuth redirects to wrong URL

Check `frontend/.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

And backend OAuth config in `backend/.env`:

```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

Registered redirect URI in Google Console must match:

```
http://localhost:3000/auth/google/callback
```

### Database has stale data: "Tests failing"

Reset and reseed:

```bash
cd backend

# Full reset
alembic downgrade base
alembic upgrade head

# Seed test data
python scripts/seed.py

# Run tests
pytest
```

## Next Steps

- [ ] Create test fixtures in `backend/conftest.py`
- [ ] Add integration tests for OAuth flows
- [ ] Set up pre-commit hooks for linting
- [ ] Configure IDE (VS Code settings, Pylance)
- [ ] Create local monitoring dashboard (Grafana)
