# Getting Started Checklist

Complete onboarding checklist for new team members joining the AI Orchestration Platform project.

## ✅ Pre-Flight (Day 0 - 1 hour)

- [ ] **Clone Repository**
  ```bash
  git clone <repo-url>
  cd ai-orchestrator
  ```

- [ ] **Read README.md** (10 minutes)
  - Understand platform overview and features
  - See architecture diagram
  - Bookmark for reference

- [ ] **Read DOCUMENTATION_INDEX.md** (10 minutes)
  - Know where to find information
  - Understand document organization

- [ ] **Setup Git**
  ```bash
  git config user.name "Your Name"
  git config user.email "your.email@company.com"
  ```

- [ ] **Create .env file for development**
  ```bash
  cp .env.example .env
  # Copy API keys from team vault/1Password
  ```

## 🚀 Local Development Setup (Day 1 - 30 minutes)

### Option A: Docker Compose (Recommended)

- [ ] **Install Docker Desktop**
  - [Download](https://www.docker.com/products/docker-desktop)
  - Verify: `docker --version`

- [ ] **Start Services**
  ```bash
  docker-compose up -d
  ```
  Wait for all services to start (2-3 minutes)

- [ ] **Verify Services**
  ```bash
  docker-compose ps
  # All should show "Up"
  
  curl http://localhost:8000/health
  # Should return {"status": "ok"}
  ```

- [ ] **Access Applications**
  - API Docs: http://localhost:8000/docs
  - Frontend: http://localhost:3000
  - Flower (Worker Monitor): http://localhost:5555
  - Database: localhost:5432 (psql or DB client)

### Option B: Native Setup (Advanced)

- [ ] Follow [LOCAL_DEV_SETUP.md](LOCAL_DEV_SETUP.md) sections:
  - Python venv setup
  - PostgreSQL installation
  - Redis installation
  - Database migrations
  - Run API, Worker, Frontend separately

## 📚 Knowledge Base (Day 1-2 - 2 hours)

### Read Based on Your Role

**All Roles** - Read First:
- [ ] [README.md](README.md) - Project overview
- [ ] [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Common commands
- [ ] [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) - Docs map

**Backend Developers** - Read Next:
- [ ] [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md) - Agent routing, providers, billing
- [ ] [backend/app/agents/](backend/app/agents/) - Review agent routing code
- [ ] [backend/app/providers/](backend/app/providers/) - Review provider implementations
- [ ] [TESTING_GUIDE.md](TESTING_GUIDE.md) - Backend testing strategy

**Frontend Developers** - Read Next:
- [ ] [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md) - API endpoints section
- [ ] [frontend/](frontend/) - Review Next.js structure
- [ ] [TESTING_GUIDE.md](TESTING_GUIDE.md) - Frontend testing strategy

**DevOps/Platform Engineers** - Read Next:
- [ ] [K8S_DEPLOYMENT.md](K8S_DEPLOYMENT.md) - Kubernetes deployment
- [ ] [k8s/](k8s/) - Review manifest files
- [ ] [helm/orchestrator/](helm/orchestrator/) - Review Helm chart
- [ ] [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Monitoring & debugging

**QA/Testers** - Read Next:
- [ ] [TESTING_GUIDE.md](TESTING_GUIDE.md) - Test architecture and examples
- [ ] [DEMO.md](DEMO.md) - Feature workflows
- [ ] [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - API commands

## 💻 Hands-On (Day 2 - 2 hours)

### Backend Developer

- [ ] **Run Backend Tests**
  ```bash
  cd backend
  pip install pytest pytest-asyncio
  pytest
  ```

- [ ] **Make Your First API Call**
  ```bash
  curl http://localhost:8000/health
  ```

- [ ] **Explore Agent Routing**
  ```bash
  # Review the code
  cat backend/app/agents/scorer.py
  
  # Look at test
  cat backend/tests/test_agents.py
  ```

- [ ] **Create a Test Task**
  - Get JWT token from OAuth or test generation
  - Create task via API: POST /api/tasks
  - Monitor in Flower: http://localhost:5555

- [ ] **Debug with Logs**
  - View API logs: `docker-compose logs -f api`
  - View Worker logs: `docker-compose logs -f worker`

### Frontend Developer

- [ ] **Run Frontend Tests**
  ```bash
  cd frontend
  npm test
  ```

- [ ] **Start Frontend Dev Server**
  ```bash
  npm run dev
  # Visit http://localhost:3000
  ```

- [ ] **Explore Components**
  ```bash
  ls -la frontend/components/
  ```

- [ ] **Make API Call from Browser**
  - Open DevTools console
  - Try: `fetch('http://localhost:8000/health').then(r => r.json())`

- [ ] **Check Type Checking**
  ```bash
  npm run type-check
  ```

### DevOps Engineer

- [ ] **Test K8s Manifests Locally**
  ```bash
  # Use k3s or kind for local K8s
  k3d cluster create
  kubectl apply -f k8s/
  ```

- [ ] **Review Helm Chart**
  ```bash
  # Dry run
  helm install orchestrator ./helm/orchestrator \
    --dry-run --debug
  ```

- [ ] **Check Docker Images**
  ```bash
  # List images
  docker images | grep orchestrator
  
  # Examine for security issues
  docker run --rm aquasec/trivy image <image>
  ```

- [ ] **Review Secrets Management**
  - Check sealed-secrets setup: `kubectl get sealedsecrets`
  - Review secret templates: `cat k8s/07-secrets-template.yaml`

### QA Engineer

- [ ] **Test Health Check Endpoint**
  ```bash
  curl http://localhost:8000/health
  curl http://localhost:8000/ops/health
  ```

- [ ] **Test OAuth Flow**
  - Visit http://localhost:3000/auth/google
  - Follow redirect and complete login
  - Check token in browser DevTools

- [ ] **Test Task Creation**
  - Create 5 tasks with different types
  - Verify status changes from pending → completed/failed

- [ ] **Test Rate Limiting**
  - Create Starter plan org
  - Submit 1001 tasks
  - Verify 1001st fails with rate limit error

## 👥 Team Sync (Day 2 - 30 minutes)

- [ ] **Attend Project Overview Meeting**
  - Ask questions about architecture
  - Understand current priorities
  - Get assigned to first task

- [ ] **Clarify Development Process**
  - Branch naming convention
  - PR review process
  - Deployment process
  - On-call procedures

- [ ] **Get Access to Tools**
  - Slack/Teams channels
  - GitHub teams membership
  - AWS/GCP console
  - Cloud provider credentials
  - API keys (OpenAI, Stripe, etc.)
  - Sentry/Monitoring dashboards

## 🔑 Environment Configuration (Day 2 - 1 hour)

- [ ] **Get API Keys from Team Vault**
  - OpenAI API key
  - Anthropic API key
  - Mistral API key
  - Stripe test/prod keys
  - Google OAuth credentials
  - GitHub OAuth credentials

- [ ] **Update .env File**
  ```bash
  # backend/.env
  OPENAI_API_KEY=sk-...
  ANTHROPIC_API_KEY=sk-ant-...
  STRIPE_SECRET_KEY=sk_test_...
  # ... etc
  ```

- [ ] **Verify Keys Work**
  ```bash
  # Test OpenAI
  curl https://api.openai.com/v1/models \
    -H "Authorization: Bearer $OPENAI_API_KEY"
  
  # Test Stripe
  curl https://api.stripe.com/v1/customers \
    -H "Authorization: Bearer $STRIPE_SECRET_KEY"
  ```

## 📖 Code Walkthroughs (Day 3 - 2 hours)

### Backend Engineer Code Path

```
backend/app/
├── main.py                    # FastAPI app, startup events
├── config.py                  # Settings, environment
├── database.py                # SQLAlchemy async setup
├── models.py                  # Database models (User, Task, etc)
└── schemas.py                 # Pydantic request/response models

agents/
├── registry.py                # Provider registration & metadata
├── scorer.py                  # Scoring formula implementation
└── router.py                  # Agent selection logic

providers/
├── executor.py                # Task executor dispatcher
├── openai_provider.py         # OpenAI implementation
├── anthropic_provider.py      # Anthropic implementation
├── mistral_provider.py        # Mistral implementation
└── scraper_provider.py        # Web scraper implementation

billing/
├── models.py                  # Plan definitions
└── service.py                 # Billing logic & webhooks

auth/
├── oauth.py                   # OAuth2 flows
├── rbac.py                    # Role-based access control
└── tokens.py                  # JWT token management

audit/
└── __init__.py                # Audit logging & verification

routes_billing.py              # Billing endpoints
routes_auth.py                 # Auth endpoints
worker.py                      # Celery configuration
```

**Suggested Reading Order:**
1. `main.py` - understand app startup
2. `models.py` - understand database schema
3. `agents/registry.py` - understand provider system
4. `agents/scorer.py` - understand scoring algorithm
5. `agents/router.py` - understand task routing
6. `providers/executor.py` - understand provider execution
7. `billing/service.py` - understand billing logic
8. `auth/rbac.py` - understand permissions

### Frontend Engineer Code Path

```
frontend/
├── pages/              # Next.js routes
│   ├── index.tsx      # Dashboard
│   ├── tasks.tsx      # Task list
│   └── auth/          # Auth pages
├── components/         # React components
│   ├── TaskList.tsx
│   ├── TaskForm.tsx
│   └── ...
├── hooks/             # Custom hooks
│   ├── useAuth.ts     # Auth state
│   ├── useTasks.ts    # Task management
│   └── useApi.ts      # API calls
├── context/           # React context
│   └── AuthContext.tsx # Auth state management
└── __tests__/         # Tests
```

**Suggested Reading Order:**
1. `hooks/useAuth.ts` - understand auth state
2. `context/AuthContext.tsx` - understand auth provider
3. `pages/index.tsx` - understand main dashboard
4. `pages/tasks.tsx` - understand task management
5. `components/TaskForm.tsx` - understand form handling
6. `hooks/useApi.ts` - understand API integration

## 🧪 Run Your First Test (Day 3 - 30 minutes)

### Backend

- [ ] **Backend Unit Test**
  ```bash
  cd backend
  pytest tests/test_agents.py::TestProviderScoring::test_score_calculation -v
  ```

- [ ] **Run All Backend Tests**
  ```bash
  pytest --cov=app
  # View coverage report: htmlcov/index.html
  ```

### Frontend

- [ ] **Frontend Unit Test**
  ```bash
  cd frontend
  npm test -- components/LoginButton
  ```

- [ ] **Type Check**
  ```bash
  npm run type-check
  ```

### Integration

- [ ] **Manual E2E Flow**
  - Go to http://localhost:3000
  - Login with OAuth
  - Create a task
  - Watch Flower for task execution
  - Check database for results

## 🚀 Deploy to Staging (Day 4)

- [ ] **Understand Staging Environment**
  - What resources exist (K8s cluster, databases)
  - Who has access
  - Deployment process (manual vs CI/CD)

- [ ] **Review Deployment Guide**
  - Read [K8S_DEPLOYMENT.md](K8S_DEPLOYMENT.md)
  - Understand kubectl and Helm commands

- [ ] **Deploy Your Code**
  1. Create feature branch
  2. Make code changes
  3. Submit PR with tests
  4. Get approval
  5. Merge to main
  6. Watch CI/CD pipeline deploy

- [ ] **Verify Deployment**
  ```bash
  # Check cluster
  kubectl get all -n orchestrator-prod
  
  # Check logs
  kubectl logs -f deployment/orchestrator-api -n orchestrator-prod
  
  # Test in staging
  curl https://staging-api.example.com/health
  ```

## 📊 Setup Monitoring & Debugging (Day 4 - 1 hour)

- [ ] **Bookmark Important URLs**
  - Local API Docs: http://localhost:8000/docs
  - Local Flower: http://localhost:5555
  - Staging API: https://staging-api.example.com
  - Production Monitoring: [team-specific URL]
  - Sentry Errors: [team-specific URL]
  - Datadog Dashboard: [team-specific URL]

- [ ] **Learn Debugging Commands**
  ```bash
  # View logs
  docker-compose logs -f api
  
  # Check database
  psql $DATABASE_URL -c "SELECT * FROM tasks LIMIT 10;"
  
  # Check Redis
  redis-cli LLEN celery
  redis-cli LRANGE celery 0 5
  
  # K8s debugging
  kubectl describe pod <pod-name>
  kubectl logs <pod-name>
  ```

- [ ] **Review TROUBLESHOOTING.md**
  - Common issues
  - Health check procedures
  - Escalation paths

## 🎯 First Task Assignment (Day 5+)

- [ ] **Receive Assignment**
  - Get issue/ticket number
  - Read requirements
  - Estimate effort
  - Ask clarifying questions

- [ ] **Plan Implementation**
  - Branch name: `feature/issue-123-short-desc`
  - Create branch: `git checkout -b feature/issue-123`
  - Identify affected files
  - Check for existing tests

- [ ] **Implement Feature**
  - Write code
  - Write tests
  - Run tests locally
  - Run linter/formatter

- [ ] **Submit PR**
  - Clear PR description
  - Link to issue
  - Request review from team
  - Address feedback
  - Merge when approved

- [ ] **Monitor Deployment**
  - Watch CI/CD pipeline
  - Check staging deployment
  - Verify in staging
  - Monitor production if auto-deployed

## 📝 Documentation Tasks

- [ ] **Update Docs for Your Changes**
  - If you modified API endpoints, update [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md)
  - If you changed deployment process, update [K8S_DEPLOYMENT.md](K8S_DEPLOYMENT.md)
  - If you found and fixed a bug, add to [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

- [ ] **Add Code Comments**
  - Complex algorithms: explain why
  - Non-obvious code: explain what
  - Keep comments up to date with code

- [ ] **Create/Update Tests**
  - Every bug fix needs a test
  - Every feature needs tests (aim for >80% coverage)

## 🔐 Security Checklist

- [ ] **API Keys**
  - Never commit credentials to git
  - Use `.env` and `.gitignore`
  - Rotate keys regularly
  - Use different keys for dev/staging/prod

- [ ] **Database**
  - Use strong passwords
  - Never run as root
  - Enable encryption at rest

- [ ] **Kubernetes**
  - Always use sealed-secrets for secrets
  - Never store plaintext secrets in git
  - Review RBAC policies
  - Use network policies

## 🤝 Team Communication

- [ ] **Join Channels**
  - #dev-engineering
  - #backend / #frontend (if separate)
  - #devops
  - #incidents

- [ ] **Ask Questions**
  - Architecture unclear? Ask in #dev-engineering
  - How does X work? Ask the team
  - Found a bug? Report in #incidents
  - Have an idea? Share in #ideas

- [ ] **Share Knowledge**
  - Pairing sessions for complex areas
  - Document gotchas you find
  - Update README with your learnings

## ✨ Week 1 Summary Check

- [ ] ✅ Cloned repo and read README
- [ ] ✅ Ran docker-compose up successfully
- [ ] ✅ Ran backend and frontend tests
- [ ] ✅ Made an API call
- [ ] ✅ Created and executed a task
- [ ] ✅ Read ADVANCED_FEATURES.md
- [ ] ✅ Attended team sync
- [ ] ✅ Got API keys configured
- [ ] ✅ Reviewed relevant code sections
- [ ] ✅ Submitted first PR
- [ ] ✅ Deployed to staging
- [ ] ✅ Got familiar with debugging tools

## 🎓 Continuous Learning

**Week 2:**
- Deep dive into your domain (backend/frontend/devops)
- Pair program with experienced team member
- Take on more complex tasks

**Month 1:**
- Contribute significantly to roadmap items
- Help onboard next team member
- Identify process improvements

**Month 3:**
- Become go-to expert in one system component
- Lead code reviews
- Mentor junior developers

## 📞 Help & Support

- **Technical Questions:** Ask in Slack #dev-engineering
- **Configuration Issues:** Check QUICK_REFERENCE.md or TROUBLESHOOTING.md
- **Deployment Issues:** Ask in #devops or check K8S_DEPLOYMENT.md
- **Bugs Found:** Report in #incidents with error logs
- **Stuck for >30 minutes:** Async pair on Slack or schedule sync

## 🎉 Welcome to the Team!

You're all set! Start with your first task and don't hesitate to ask questions. The team is here to help you succeed.

**Next Steps:**
1. Close this checklist
2. Verify `docker-compose ps` shows all services running
3. Visit http://localhost:3000 and explore
4. Ask your tech lead for your first task
5. Have fun building! 🚀
