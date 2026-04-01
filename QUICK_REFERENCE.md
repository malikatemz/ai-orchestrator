# Quick Reference Guide

Fast lookup for the most common commands and patterns.

## Environment Setup

### Docker Compose (Recommended for Local Dev)

```bash
# Clone and start
git clone <repo>
cd ai-orchestrator
cp .env.example .env
docker-compose up -d

# Services available immediately
# API:      http://localhost:8000
# Frontend: http://localhost:3000
# Docs:     http://localhost:8000/docs
# Flower:   http://localhost:5555

# View logs
docker-compose logs -f api
docker-compose logs -f worker

# Stop everything
docker-compose down
```

## Backend Development

### Python Virtual Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows
```

### Dependency Management

```bash
# Install
pip install -r requirements.txt

# Add new package
pip install package-name
pip freeze > requirements.txt
```

### Database Operations

```bash
# Migration
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade base

# SQL access
psql orchestrator -U orchestrator
```

### API Development

```bash
# Start API with hot reload
uvicorn app.main:app --reload --port 8000

# Test endpoint
curl -X GET http://localhost:8000/health

# With auth token
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://localhost:8000/api/tasks
```

### Celery Worker

```bash
# Start worker
celery -A app.worker worker --loglevel=info

# Monitor in Flower
celery -A app.worker flower --port=5555
# Access: http://localhost:5555

# Debug mode
celery -A app.worker worker --loglevel=debug

# Check queue status
redis-cli LLEN celery
redis-cli LRANGE celery 0 10
```

### Testing

```bash
# Run all tests
pytest

# Specific test file
pytest tests/test_agents.py -v

# Specific test
pytest tests/test_agents.py::TestProviderScoring::test_score_calculation -v

# With coverage
pytest --cov=app --cov-report=html

# Watch mode
pytest-watch

# Parallel execution
pytest -n auto
```

### Code Quality

```bash
# Format
black app/
isort app/

# Lint
flake8 app/
pylint app/

# Type check
mypy app/
```

## Frontend Development

### Setup

```bash
cd frontend
npm install

# Keep environment variables in .env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

### Development Server

```bash
# Start with hot reload
npm run dev

# Access: http://localhost:3000

# Build for production
npm run build
npm start
```

### Testing

```bash
# Jest tests
npm test

# Watch mode
npm test -- --watch

# Coverage
npm test -- --coverage

# Specific test file
npm test -- components/LoginButton
```

### Code Quality

```bash
# Type check
npm run type-check

# Lint
npm run lint

# Format
npm run format
```

## Kubernetes & Helm

### Prerequisites

```bash
# Check kubectl
kubectl version --client

# Check Helm
helm version

# Configure kubeconfig
kubectl config use-context cluster-name
```

### Direct kubectl Deployment

```bash
# Deploy all manifests
kubectl apply -f k8s/

# Check status
kubectl get all -n orchestrator-prod

# Watch pods
kubectl get pods -n orchestrator-prod -w

# View logs
kubectl logs -f deployment/orchestrator-api -n orchestrator-prod

# Port forward
kubectl port-forward svc/orchestrator-api 8000:8000 -n orchestrator-prod

# Scale manually
kubectl scale deployment/orchestrator-api --replicas=5 -n orchestrator-prod

# Delete everything
kubectl delete namespace orchestrator-prod
```

### Helm Deployment

```bash
# Add repo (if using charts repo)
helm repo add myrepo https://...
helm repo update

# Install
helm install orchestrator ./helm/orchestrator \
  -f values-prod.yaml \
  -n orchestrator-prod \
  --create-namespace

# Upgrade
helm upgrade orchestrator ./helm/orchestrator \
  -f values-prod.yaml

# Check status
helm status orchestrator -n orchestrator-prod

# Rollback
helm rollback orchestrator 1

# Uninstall
helm uninstall orchestrator -n orchestrator-prod
```

## Docker

### Build Images

```bash
# API
docker build -t orchestrator-api:v1.0.0 -f backend/Dockerfile backend/

# Worker
docker build -t orchestrator-worker:v1.0.0 -f backend/Dockerfile.worker backend/

# Frontend
docker build -t orchestrator-frontend:v1.0.0 frontend/
```

### Push to Registry

```bash
# Login
docker login ghcr.io
# or
aws ecr get-login-password | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag
docker tag orchestrator-api:v1.0.0 ghcr.io/myorg/orchestrator-api:v1.0.0

# Push
docker push ghcr.io/myorg/orchestrator-api:v1.0.0
```

## Git Workflow

### Daily Work

```bash
# Check status
git status

# View diff
git diff

# Stage changes
git add .

# Commit
git commit -m "feat: describe feature"

# Push
git push origin main

# Pull latest
git pull origin main

# Create branch
git checkout -b feature/feature-name

# Switch branch
git checkout main

# Merge branch
git merge feature/feature-name

# Delete branch
git branch -d feature/feature-name
```

## API Endpoints Quick Lookup

```bash
# Health
curl http://localhost:8000/health

# API Docs (interactive)
curl http://localhost:8000/docs

# Create Task (requires auth)
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"summarize","input":"text"}'

# Get Tasks
curl -H "Authorization: Bearer $JWT" \
  http://localhost:8000/api/tasks

# OAuth Google
curl http://localhost:8000/auth/google

# Refresh Token
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"..."}'

# Billing Usage
curl -H "Authorization: Bearer $JWT" \
  http://localhost:8000/api/billing/usage
```

## Environment Variables (Common)

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/orchestrator

# Redis
REDIS_URL=redis://localhost:6379

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Stripe (test)
STRIPE_SECRET_KEY=sk_test_...

# OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# JWT
JWT_SECRET_KEY=your-secret-key-here

# App
APP_MODE=dev
LOG_LEVEL=DEBUG
```

## Debugging Checklist

### API Won't Start

```bash
# Check if port is in use
lsof -i :8000

# Check database connection
psql orchestrator -U orchestrator

# Check Python syntax
python -m py_compile app/main.py

# Start with debug logging
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

### Database Issues

```bash
# Check connection
psql $DATABASE_URL -c "SELECT 1"

# Check tables
psql orchestrator -U orchestrator -c "\dt"

# Reset database
dropdb orchestrator
createdb orchestrator
alembic upgrade head
```

### Worker Not Processing

```bash
# Check Redis
redis-cli ping

# Check queue
redis-cli LLEN celery

# View pending tasks
redis-cli LRANGE celery 0 -1

# Restart worker
pkill -f "celery.*worker"
celery -A app.worker worker --loglevel=info
```

### K8s Pod Issues

```bash
# Describe pod for events
kubectl describe pod name -n orchestrator-prod

# View logs
kubectl logs pod-name -n orchestrator-prod

# View previous logs (if crashed)
kubectl logs pod-name --previous -n orchestrator-prod

# Get shell access
kubectl exec -it pod-name -n orchestrator-prod -- /bin/sh

# Check resources
kubectl top pods -n orchestrator-prod
```

## Performance Profiling

```bash
# Python CPU profile
python -m cProfile -s cumulative app/main.py

# Memory profile
pip install memory-profiler
python -m memory_profiler app/main.py

# Load test
pip install locust
locust -f tests/performance/locustfile.py -H http://localhost:8000

# Database slow queries
# In PostgreSQL:
CREATE EXTENSION pg_stat_statements;
SELECT query, calls, total_time FROM pg_stat_statements \
  ORDER BY total_time DESC LIMIT 10;
```

## Useful One-Liners

```bash
# Find all TODO comments in code
grep -r "TODO" backend/ frontend/ --include="*.py" --include="*.ts" --include="*.tsx"

# Count lines of code
find backend -name "*.py" | xargs wc -l | tail -1
find frontend -name "*.tsx" -o -name "*.ts" | xargs wc -l | tail -1

# Docker cleanup
docker system prune -a  # Remove unused images/containers

# Kill all containers
docker ps -q | xargs docker kill

# Show git log oneline
git log --oneline

# Count commits
git rev-list --count HEAD

# List branches
git branch -a

# Release checklist
git tag v1.0.0
git push origin v1.0.0
```

## Common Issues & Quick Fixes

| Issue | Solution |
|-------|----------|
| Port already in use | `lsof -i :PORT` then `kill PID` or use different port |
| Token expired | Use refresh endpoint or login again |
| Database locked | Kill blocking connection: `SELECT pg_terminate_backend(pid) FROM ...` |
| Queue stuck | `redis-cli FLUSHDB` (careful!) or restart worker |
| Pod pending | Check: `kubectl describe node` for resource availability |
| Ingress 502 | Check backend service: `kubectl get endpoints` |
| CORS error | Verify frontend URL in backend cors_origins config |
| Docker image not found | Run `docker pull image:tag` or build locally |

## Documentation Links

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [README.md](README.md) | Overview & quick start | 10 min |
| [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md) | Feature deep dive | 60 min |
| [LOCAL_DEV_SETUP.md](LOCAL_DEV_SETUP.md) | Development instructions | 30 min |
| [K8S_DEPLOYMENT.md](K8S_DEPLOYMENT.md) | Production deployment | 45 min |
| [TESTING_GUIDE.md](TESTING_GUIDE.md) | Testing strategy | 40 min |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Debugging guide | Reference |
| [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) | All docs index | 15 min |

## Status Commands

```bash
# Everything in one go (Docker Compose)
docker-compose ps

# Backend health
curl http://localhost:8000/health

# Database
psql orchestrator -U orchestrator -c "SELECT count(*) FROM pg_stat_activity;"

# Redis
redis-cli info stats

# Kubernetes cluster
kubectl get nodes
kubectl get all -n orchestrator-prod

# Container images
docker images | grep orchestrator
```

## Next Steps

- [ ] Follow [LOCAL_DEV_SETUP.md](LOCAL_DEV_SETUP.md) for your environment
- [ ] Run `docker-compose up` to start
- [ ] Visit http://localhost:8000/docs to explore API
- [ ] Check [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md) for system details
- [ ] Run `pytest` to verify backend
- [ ] Run `npm test` to verify frontend
