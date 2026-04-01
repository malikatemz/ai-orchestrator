# Documentation Index

Complete guide to all documentation in the AI Orchestration Platform project.

## 📚 Core Documentation

### [README.md](README.md)
**Start here!** Overview of the platform, quick start guide, tech stack, architecture diagram, and API endpoints.

**Covers:**
- Feature overview
- Tech stack
- Quick start (Docker Compose vs Local)
- Architecture diagram
- API endpoints summary

**Read time: 10 minutes**

---

## 🎯 Getting Started

### [LOCAL_DEV_SETUP.md](LOCAL_DEV_SETUP.md)
Complete guide for setting up local development environment with native tools (Python, Node.js, PostgreSQL, Redis).

**Covers:**
- Docker Compose setup (single command)
- Native Python backend setup
- Database configuration
- Frontend setup
- Development workflow
- Testing with pytest
- Debugging with pdb and VS Code
- Common development tasks
- Troubleshooting

**Read time: 30 minutes**

---

## 🚀 Deployment

### [K8S_DEPLOYMENT.md](K8S_DEPLOYMENT.md)
Production Kubernetes deployment guide with step-by-step instructions for kubectl and Helm.

**Covers:**
- Prerequisites and architecture
- Preparing Docker images
- Configuring secrets (sealed-secrets recommended)
- Direct kubectl deployment (8 YAML files)
- Helm chart deployment
- Verification procedures
- Database migrations
- Scaling strategies
- Backup and recovery
- Troubleshooting K8s issues

**Read time: 45 minutes**

---

### [DEPLOYMENT.md](DEPLOYMENT.md)
General deployment strategies, checklist, and best practices (pre-existing docs).

---

## 🧪 Testing & Quality

### [TESTING_GUIDE.md](TESTING_GUIDE.md)
Comprehensive testing strategy including unit, integration, E2E, and performance testing.

**Covers:**
- Backend test structure (conftest.py fixtures)
- Unit tests: agent routing, provider scoring, billing
- Integration tests: OAuth flows, task execution
- Frontend component and hook tests
- Performance testing with Locust
- GitHub Actions CI/CD workflow
- Test coverage goals and metrics
- Running tests with pytest and npm

**Read time: 40 minutes**

---

## 🔧 Troubleshooting & Monitoring

### [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
Quick diagnostics and solutions for common issues in all environments.

**Covers:**
- Health check script
- Database connection issues
- Redis connectivity problems
- API startup errors
- Worker task processing issues
- Provider timeouts and fallback chains
- Billing and rate limiting issues
- OAuth configuration problems
- Kubernetes pod issues (Pending, CrashLoopBackOff)
- Ingress routing problems
- Comprehensive troubleshooting matrix
- Monitoring setup (Prometheus, Grafana)
- Alert rules
- Performance tuning checklist
- Escalation paths

**Read time: 50 minutes** (reference document - use as needed)

---

## 📖 Feature Deep Dives

### [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md)
Detailed explanation of all enterprise features with examples and code samples.

**Covers:**
- Agent routing algorithm with scoring formula
- Multi-provider execution with fallback chain
- Stripe billing integration (plans, webhooks)
- OAuth flows (Google, GitHub, SAML)
- RBAC permission matrix (5 roles)
- JWT token management
- Audit logging with hash chaining
- Celery worker task execution
- API endpoint specifications
- Configuration reference

**Read time: 60 minutes** (reference document)

---

### [ARCHITECTURE.md](ARCHITECTURE.md)
System architecture, component interactions, and design decisions (pre-existing docs).

---

## 🎬 Demos & Examples

### [DEMO.md](DEMO.md)
Walkthrough of key features with example requests, responses, and expected outputs (pre-existing docs).

---

## 🛣️ Future Work

### [ROADMAP.md](ROADMAP.md)
Planned features, enhancements, and timeline (pre-existing docs).

---

## 🚨 Production

### [PRODUCTION_DEBUGGING.md](PRODUCTION_DEBUGGING.md)
Production-specific debugging techniques and logs analysis (pre-existing docs).

---

### [ERROR_HANDLING.md](ERROR_HANDLING.md)
Error codes, messages, and handling strategies (pre-existing docs).

---

## 📋 Config Files

### [.env.production.example](.env.production.example)
Production environment variables template. Copy to `.env.production` and fill in actual values.

**Variables:**
- Database: `DATABASE_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`
- Redis: `REDIS_URL`
- API Keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`
- Billing: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- Auth: `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GITHUB_CLIENT_ID`, etc.
- App: `APP_MODE`, `LOG_LEVEL`, `SENTRY_DSN`
- Kubernetes: `API_DOMAIN`, `APP_DOMAIN`

---

## 🐳 Docker & Compose

### [docker-compose.yml](docker-compose.yml)
Development Docker Compose setup with all services (PostgreSQL, Redis, API, Worker, Flower, Frontend).

**Services:**
- PostgreSQL 15 (port 5432)
- Redis 7 (port 6379)
- FastAPI (port 8000, auto-reload)
- Celery Worker (with 4 concurrency)
- Flower UI (port 5555)
- Next.js Frontend (port 3000, fast-refresh)

**Commands:**
```bash
docker-compose up -d        # Start all
docker-compose logs -f api  # View logs
docker-compose down         # Stop all
```

---

### [docker-compose.prod.yml](docker-compose.prod.yml)
Production-optimized Docker Compose with resource limits and health checks (pre-existing).

---

## ☸️ Kubernetes

### [k8s/](k8s/)
Complete set of Kubernetes manifests organized by component:

1. **[00-namespace-rbac.yaml](k8s/00-namespace-rbac.yaml)** - Namespace creation and RBAC (ServiceAccounts, Roles, RoleBindings)
2. **[01-database-redis.yaml](k8s/01-database-redis.yaml)** - PostgreSQL and Redis StatefulSets (10Gi + 5Gi storage)
3. **[02-api-deployment.yaml](k8s/02-api-deployment.yaml)** - FastAPI Deployment (2 replicas, health checks)
4. **[03-worker-deployment.yaml](k8s/03-worker-deployment.yaml)** - Celery Worker Deployment (queue routing)
5. **[04-frontend-deployment.yaml](k8s/04-frontend-deployment.yaml)** - Next.js Frontend Deployment
6. **[05-hpa.yaml](k8s/05-hpa.yaml)** - Horizontal Pod Autoscaling (CPU-based)
7. **[06-ingress.yaml](k8s/06-ingress.yaml)** - Nginx Ingress with TLS
8. **[07-secrets-template.yaml](k8s/07-secrets-template.yaml)** - Secret reference (use sealed-secrets in prod)
9. **[08-keda-scaler.yaml](k8s/08-keda-scaler.yaml)** - KEDA queue-depth autoscaling

---

### [helm/](helm/)
Helm chart for templated Kubernetes deployment:

- **[Chart.yaml](helm/orchestrator/Chart.yaml)** - Chart metadata
- **[values.yaml](helm/orchestrator/values.yaml)** - Default configuration (50+ options)
- **[templates/](helm/orchestrator/templates/)** - Namespace, ConfigMap, Secrets templates

**Install:**
```bash
helm install orchestrator ./helm/orchestrator -f values-prod.yaml
```

---

## 🔄 CI/CD

### [.github/workflows/](https://github.com/.../tree/main/.github/workflows)
GitHub Actions workflows for automated testing and deployment:

- **[deploy-k8s.yml](.github/workflows/deploy-k8s.yml)** - Build, test, deploy to K8s
  - Builds API, Worker, Frontend images
  - Runs pytest (backend) and npm test (frontend)
  - Deploys via Helm
  - Verifies rollout success

---

## 📂 Project Structure

```
.
├── README.md                          # Start here!
├── ADVANCED_FEATURES.md               # Feature documentation (60 min)
├── ARCHITECTURE.md                    # System design
├── TESTING_GUIDE.md                   # Testing strategy (40 min)
├── TROUBLESHOOTING.md                 # Debugging & monitoring (reference)
├── LOCAL_DEV_SETUP.md                 # Local development (30 min)
├── K8S_DEPLOYMENT.md                  # K8s deployment (45 min)
├── ERROR_HANDLING.md                  # Error reference
├── PRODUCTION_DEBUGGING.md            # Prod debugging
├── ROADMAP.md                         # Future features
├── DEMO.md                            # Feature walkthrough
│
├── backend/                           # FastAPI + Celery
│   ├── app/
│   │   ├── main.py                   # FastAPI app entry
│   │   ├── config.py                 # Settings
│   │   ├── database.py               # SQLAlchemy setup
│   │   ├── models.py                 # DB models
│   │   ├── schemas.py                # Pydantic schemas
│   │   ├── agents/
│   │   │   ├── registry.py           # Provider registration
│   │   │   ├── scorer.py             # Scoring formula
│   │   │   └── router.py             # Agent selection
│   │   ├── providers/
│   │   │   ├── executor.py           # Task executor
│   │   │   ├── openai_provider.py    # OpenAI client
│   │   │   ├── anthropic_provider.py # Anthropic client
│   │   │   ├── mistral_provider.py   # Mistral client
│   │   │   └── scraper_provider.py   # Web scraper
│   │   ├── billing/
│   │   │   ├── models.py             # Plan definitions
│   │   │   └── service.py            # Billing logic
│   │   ├── auth/
│   │   │   ├── oauth.py              # OAuth flows
│   │   │   ├── rbac.py               # Role permissions
│   │   │   └── tokens.py             # JWT management
│   │   ├── audit/                    # Audit logging
│   │   ├── routes_*.py               # API endpoints
│   │   └── worker.py                 # Celery setup
│   ├── tests/                        # Test suite
│   ├── requirements.txt               # Dependencies
│   └── Dockerfile, Dockerfile.worker # Container images
│
├── frontend/                          # Next.js + TypeScript
│   ├── pages/                        # Next.js routes
│   ├── components/                   # React components
│   ├── hooks/                        # Custom hooks
│   ├── context/                      # Auth context
│   ├── __tests__/                    # Frontend tests
│   ├── package.json                  # Dependencies
│   └── Dockerfile                    # Container image
│
├── k8s/                              # Kubernetes manifests
│   ├── 00-namespace-rbac.yaml
│   ├── 01-database-redis.yaml
│   ├── 02-api-deployment.yaml
│   ├── 03-worker-deployment.yaml
│   ├── 04-frontend-deployment.yaml
│   ├── 05-hpa.yaml
│   ├── 06-ingress.yaml
│   ├── 07-secrets-template.yaml
│   └── 08-keda-scaler.yaml
│
├── helm/                             # Helm chart
│   └── orchestrator/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│
├── .github/                          # GitHub Actions
│   └── workflows/
│       └── deploy-k8s.yml
│
├── .env.example                      # Dev env template
├── .env.production.example           # Prod env template
├── docker-compose.yml                # Dev compose
└── docker-compose.prod.yml           # Prod compose
```

---

## 🎓 Learning Path

**For New Developers:**
1. Start with [README.md](README.md) (10 min)
2. Run [LOCAL_DEV_SETUP.md](LOCAL_DEV_SETUP.md) with Docker Compose (5 min setup)
3. Explore API at http://localhost:8000/docs (5 min)
4. Read [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md) to understand scoring and routing (30 min)
5. Check [TESTING_GUIDE.md](TESTING_GUIDE.md) to write your first test (15 min)

**For DevOps/Platform Engineers:**
1. Read [ARCHITECTURE.md](ARCHITECTURE.md) (15 min)
2. Review [K8S_DEPLOYMENT.md](K8S_DEPLOYMENT.md) (45 min)
3. Check Helm chart in [helm/](helm/) (10 min)
4. Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md) monitoring section (15 min)

**For QA/Testers:**
1. Read [LOCAL_DEV_SETUP.md](LOCAL_DEV_SETUP.md) (30 min)
2. Run Docker Compose (5 min)
3. Review [TESTING_GUIDE.md](TESTING_GUIDE.md) (40 min)
4. Check [DEMO.md](DEMO.md) for feature workflows (20 min)

**For Product Managers:**
1. Read [README.md](README.md) (10 min)
2. Check [ROADMAP.md](ROADMAP.md) (15 min)
3. Review [DEMO.md](DEMO.md) for feature showcase (20 min)

---

## 🔗 Cross-References

### By Feature

**Agent Routing:**
- Implementation: [backend/app/agents/](backend/app/agents/)
- How it works: [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md) - Agent Routing section
- Testing: [TESTING_GUIDE.md](TESTING_GUIDE.md) - Unit Tests: Agent Routing

**Billing:**
- Implementation: [backend/app/billing/](backend/app/billing/)
- API endpoints: [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md) - Billing section
- Testing: [TESTING_GUIDE.md](TESTING_GUIDE.md) - Unit Tests: Billing

**Authentication:**
- Implementation: [backend/app/auth/](backend/app/auth/)
- OAuth flows: [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md) - OAuth section
- Testing: [TESTING_GUIDE.md](TESTING_GUIDE.md) - Integration Tests: OAuth

**Audit Logs:**
- Implementation: [backend/app/audit/](backend/app/audit/)
- How it works: [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md) - Audit Logging section
- Testing: [TESTING_GUIDE.md](TESTING_GUIDE.md) - Integration Tests

**Kubernetes:**
- Manifests: [k8s/](k8s/)
- Deployment guide: [K8S_DEPLOYMENT.md](K8S_DEPLOYMENT.md)
- Helm chart: [helm/orchestrator/](helm/orchestrator/)

**Docker:**
- Dev setup: [docker-compose.yml](docker-compose.yml)
- Prod setup: [docker-compose.prod.yml](docker-compose.prod.yml)
- Images: [backend/Dockerfile](backend/Dockerfile), [frontend/Dockerfile](frontend/Dockerfile)

---

## 📞 Quick Links

- **API Docs**: http://localhost:8000/docs (when running)
- **Flower (Worker monitoring)**: http://localhost:5555 (when running)
- **Frontend**: http://localhost:3000 (when running)
- **Health Check**: http://localhost:8000/health (when running)

---

## ✅ Checklist for New Deployments

- [ ] Read README.md
- [ ] Review ADVANCED_FEATURES.md
- [ ] Set up local dev (LOCAL_DEV_SETUP.md)
- [ ] Run tests (TESTING_GUIDE.md)
- [ ] Plan deployment (K8S_DEPLOYMENT.md)
- [ ] Review TROUBLESHOOTING.md monitoring section
- [ ] Configure secrets (sealed-secrets)
- [ ] Review ROADMAP.md for upcoming features
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Plan backups strategy
- [ ] Document any custom modifications

---

## 📝 Contributing

When adding new features:
1. Update relevant `.md` files in the docs/
2. Add tests per TESTING_GUIDE.md
3. Update API documentation in ADVANCED_FEATURES.md
4. Test locally with docker-compose
5. Test K8s deployment in staging cluster
6. Update ROADMAP.md with completion status

---

## 📄 Document Maintenance

**Last Updated**: [Generated by AI Orchestrator platform docs generator]

Documents in this index are kept in sync with the codebase. When code changes significantly, corresponding documentation should be updated.

**Guidelines:**
- Keep docs DRY - reference other docs instead of repeating
- Use examples from actual code when possible
- Update timestamps and version numbers
- Link across documents extensively
- Maintain clear reading time estimates
