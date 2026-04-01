# AI Orchestration Platform - Advanced Features Guide

This document covers the enterprise advanced features added in this phase.

## Architecture Overview

```
┌─────────────────┐
│   Frontend      │ (Next.js 14, OAuth login, task dashboard)
│   (Next.js 14)  │
└────────┬────────┘
         │
         ├─ /health
         ├─ /app-config (demo/auth mode)
         ├─ /workflows, /tasks
         ├─ /auth/* (OAuth callback)
         ├─ /billing/* (checkout, usage)
         └─ /ops/* (audit logs, metrics)
         │
┌────────▼────────────────┐
│  FastAPI Backend        │
│  - Agent Router         │
│  - Provider Executor    │
│  - Billing Integration  │
│  - RBAC + Audit Log     │
└────────┬────────────────┘
         │
    ┌────┴──────┬─────────┐
    │            │         │
┌───▼──┐  ┌──────▼──┐   ┌─▼─────┐
│Redis │  │PostgreSQL│  │Stripe │
└──────┘  └──────────┘  └───────┘
    │
    └─▶ Celery Worker
        - Select Provider (agent routing)
        - Execute via OpenAI/Anthropic/Mistral
        - Fallback chain on failure
```

## 1. Agent Routing System

The platform now selects the best provider for each task based on performance history.

### Provider Registry

Located in `/backend/app/agents/registry.py`:

```python
PROVIDER_REGISTRY = {
    "openai-gpt4o": AgentProvider(
        id="openai-gpt4o",
        model_id="gpt-4o",
        cost_per_1k_tokens=0.005,
        avg_latency_ms=800,
        supports_types=["summarize", "classify", "extract", "analyze"],
    ),
    "anthropic-sonnet": AgentProvider(...),
    "mistral-small": AgentProvider(...),
    "scraper": AgentProvider(...),  # No API key needed
}
```

### Scoring Heuristic

The scorer in `/backend/app/agents/scorer.py` uses:

```
score = (success_rate * 0.5) + (speed_score * 0.3) + (cost_score * 0.2)
```

- **Success Rate (50%)**: Historical success rate from `agent_stats` table
- **Speed (30%)**: Inverse of normalized latency across all candidates
- **Cost (20%)**: Inverse of normalized cost

### Router Fallback Chain

When a provider fails, the router automatically retries with next-best provider:

```python
select_agent(db, "summarize")  # Returns (selected, [alternatives])
# If selected fails:
failing_providers = ["openai-gpt4o"]
select_agent(db, "summarize", exclude_providers=failing_providers)
# Try next best...
```

Max 3 fallbacks per task execution.

### Agent Stats Tracking

Each task execution records stats for future scoring:

```sql
INSERT INTO agent_stats (org_id, provider_id, task_type, success, latency_ms, cost_usd)
VALUES ('{org_id}', 'openai-gpt4o', 'summarize', true, 450, 0.0015)
```

## 2. Multi-Provider LLM Execution

Providers implemented in `/backend/app/providers/`:

### OpenAI Provider
- Models: GPT-4o, GPT-4o-mini
- Cost-effective, fast
- Supports: summarize, classify, extract, analyze

### Anthropic Provider
- Model: Claude 3.5 Sonnet
- Best for complex reasoning
- Supports: summarize, analyze, extract, classify

### Mistral Provider
- Model: Mistral Small
- Most cost-effective
- Supports: summarize, classify, extract

### Web Scraper (Native)
- No API key needed
- Uses: httpx + BeautifulSoup
- Supports: scrape

## 3. Stripe Billing Integration

### Subscription Plans

**Starter:** $29/month - 1,000 tasks
**Pro:** $99/month - 10,000 tasks
**Enterprise:** Custom pricing

### Checkout Flow

```python
# 1. User selects plan
POST /billing/checkout
{
  "plan": "pro",
  "success_url": "https://app.example.com/success",
  "cancel_url": "https://app.example.com/cancel"
}

# 2. Redirect to Stripe Checkout (session.url)

# 3. Webhook: checkout.session.completed
# → org.subscription_status = "active"
# → org.stripe_customer_id = "cus_..."
```

### Usage Metering

After each completed task:

```python
report_usage(db, org_id, stripe_subscription_item_id, quantity=1)
```

Stripe automatically tracks monthly usage against plan limits.

### Rate Limiting

Enforce via dependency:

```python
from ..billing import enforce_rate_limit

@router.post("/tasks")
async def create_task(task: TaskCreate, db = Depends(get_db)):
    enforce_rate_limit(db, current_user["org_id"])  # Raises BillingError if over limit
    ...
```

## 4. Enterprise Authentication & RBAC

### OAuth Providers

**Google OAuth2:**
```
GET /auth/google → Redirect to Google
GET /auth/google/callback?code=...&state=... → Upsert user, create org, return JWT
```

**GitHub OAuth2:**
```
GET /auth/github → Redirect to GitHub
GET /auth/github/callback?code=...&state=... → Same flow
```

**SAML 2.0 (Stub):**
```
GET /auth/saml/metadata → Return placeholder XML
# Configure with actual IdP (Okta, Azure AD, etc.) using python3-saml
```

### Role-Based Access Control (RBAC)

5 roles with permission matrix:

| Role | Permissions |
|------|-------------|
| **Owner** | All permissions |
| **Admin** | manage_users, run_workflows, view_logs, view_metrics |
| **Member** | run_workflows, view_own_logs |
| **Viewer** | view_logs (read-only) |
| **BillingAdmin** | view_billing, manage_subscription |

### Usage in Routes

```python
from ..auth.rbac import require_permission, Permission

@router.get("/admin/users")
async def admin_users(current_user = Depends(get_current_user)):
    require_permission(current_user["role"], Permission.MANAGE_USERS)
    # If permission denied → PermissionError (403)
    ...
```

### Token Management

- **Access Token:** 15 minutes expiry (JWT)
- **Refresh Token:** 7 days expiry (stored in httpOnly cookie)

```python
# Issue tokens on OAuth callback
access_token = create_access_token(user)
refresh_token = create_refresh_token(user)

# Refresh endpoint
POST /auth/refresh
{ "refresh_token": "..." }
→ { "access_token": "..." }

# Logout (revoke refresh token)
POST /auth/logout
{ "refresh_token": "..." }
```

## 5. Tamper-Evident Audit Logs

Every action creates a hash-chained audit log entry.

### Hash Verification

```python
from ..audit import log_event, verify_audit_chain

# Log action
log_event(
    db=db,
    user_id=user_id,
    org_id=org_id,
    action="task.completed",
    resource_type="task",
    resource_id=123,
    details={"provider": "gpt4o", "cost": 0.001},
)

# Verify chain (detect tampering)
result = verify_audit_chain(db, org_id)
print(result)  # {"valid": true, "broken_at": null, "total_checked": 150}
```

### Chain Structure

Each row includes:
- `row_hash`: SHA256(id + user_id + action + timestamp + details + previous_hash)
- `previous_hash`: Links to prior row's hash

If any row is modified, hash verification fails, exposing tampering.

## 6. Kubernetes Deployment

### Manifest Structure

```
k8s/
├── 00-namespace-rbac.yaml       # Namespace, RBAC
├── 01-database-redis.yaml       # Postgres, Redis (StatefulSets)
├── 02-api-deployment.yaml       # FastAPI (2 replicas)
├── 03-worker-deployment.yaml    # Celery worker (2 replicas)
├── 04-frontend-deployment.yaml  # Next.js (2 replicas)
├── 05-hpa.yaml                  # Autoscaling rules
├── 06-ingress.yaml              # Nginx Ingress + cert-manager
├── 07-secrets-template.yaml     # Encrypted secrets (sealed-secrets)
└── 08-keda-scaler.yaml          # Queue-based scaling
```

### Apply Manifests

```bash
# 1. Encrypt secrets (production)
echo -n "postgresql://..." | kubeseal -n orchestrator-prod -o yaml > secrets.sealed.yaml

# 2. Apply all manifests
kubectl apply -f k8s/

# 3. Verify
kubectl get pods -n orchestrator-prod
kubectl describe ingress orchestrator-ingress -n orchestrator-prod
```

### Helm Chart

Alternative: Use Helm for templated deployment

```bash
helm install orchestrator ./helm/orchestrator \
  --set global.domain=example.com \
  --set images.api.tag=v1.0.0
```

### Auto-scaling

**CPU-based** (standard):
- API: min 2, max 10, target 60% CPU
- Worker: min 2, max 20, target 70% CPU

**Queue-depth-based** (KEDA):
```yaml
ScaledObject: Celery queue length > 50 → scale up workers
```

## 7. Celery Worker Integration

### Task Execution Flow

```
User POST /tasks
  ↓
create_and_queue_task(db, task_payload)
  ↓
Celery queue (Redis)
  ↓
Worker receives: execute_task_async(task_id, org_id, task_type, input_json)
  ↓
1. select_agent(task_type) → Choose provider via scoring
  ↓
2. execute_task(provider, task_type, input_json)
   - If success: Update task.status=completed, record usage
   - If failure: Try fallback providers (up to 3 total)
   - If all fail: task.status=failed
  ↓
3. log_event(action="task.completed|task.failed")
  ↓
4. record_provider_usage() → Feed agent_stats for next scoring
```

### Queues

Router supports 3 priority queues:

- **high_priority:** Critical tasks, faster latency allowed
- **default:** Most tasks
- **low_cost:** Low priority, prefer cheapest provider

## 8. Deployment Secrets Management

### Local Development

```bash
# .env.example
OPENAI_API_KEY={your-key}
STRIPE_SECRET_KEY={your-key}
GOOGLE_CLIENT_ID={your-id}
```

### Production (Sealed Secrets)

```bash
# Install sealed-secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.18.0/controller.yaml

# Encrypt secrets
echo -n "DATABASE_URL=postgresql://..." | kubeseal -n orchestrator-prod -o yaml

# Sealed secret is safe to commit to git
```

## 9. Monitoring & Observability

### Metrics Endpoints

```
GET /ops/metrics
{
  "execution_lanes": [
    {"queue_name": "high_priority", "task_count": 5, "success_rate": 0.98},
    {"queue_name": "default", "task_count": 150, "success_rate": 0.95},
  ],
  "total_tasks": 155,
  "overall_success_rate": 0.955
}
```

### Audit Log Verification

```
GET /audit/verify
{
  "valid": true,
  "broken_at": null,
  "total_checked": 1200
}
```

### Sentry Integration

All errors automatically reported to Sentry:

```python
sentry_sdk.init("https://key@sentry.io/project")
```

## 10. Quick Start

### 1. Install Dependencies

```bash
pip install -r backend/requirements.txt
npm install --prefix frontend
```

### 2. Configure Environment

```bash
cp backend/.env.example backend/.env
# Fill in API keys, database URL, etc.
```

### 3. Initialize Database

```bash
cd backend
alembic upgrade head
python -m app.services seed_demo_data  # Optional demo data
```

### 4. Run Locally

```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2: Worker
cd backend
celery -A app.worker worker -l info

# Terminal 3: Frontend
cd frontend
npm run dev

# Navigate to http://localhost:3000
```

### 5. Deploy to K8s

```bash
# Build images
docker build -t orchestrator-api:v1 -f backend/Dockerfile backend/
docker build -t orchestrator-worker:v1 -f backend/Dockerfile.worker backend/
docker build -t orchestrator-frontend:v1 frontend/

# Push to registry
docker push ...

# Deploy
kubectl apply -f k8s/
helm upgrade --install orchestrator ./helm/orchestrator
```

## Configuration Reference

### Environment Variables

**Database:**
- `DATABASE_URL`: PostgreSQL conn string
- `REDIS_URL`: Redis conn string

**Agents:**
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `MISTRAL_API_KEY`: Mistral API key

**Billing:**
- `STRIPE_SECRET_KEY`: Stripe secret key
- `STRIPE_WEBHOOK_SECRET`: Webhook signing secret

**OAuth:**
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`

**JWT:**
- `JWT_SECRET_KEY`: Secret for token signing
- `JWT_ALGORITHM`: Algorithm (default: HS256)

**App:**
- `APP_MODE`: "demo" or "auth"
- `PUBLIC_DEMO_MODE`: Enable public demo

## Troubleshooting

### Task execution failing for all providers

1. Check agent_stats table for success rate of each provider
2. Verify API keys are set correctly
3. Check provider status (rate limits, quota)
4. Look at audit logs for detailed error

### OAuth callback not working

1. Verify OAuth app is registered with provider
2. Check redirect URI matches in /auth/oauth.py
3. Verify CLIENT_ID and CLIENT_SECRET are set
4. Check Sentry dashboard for OAuth errors

### Stripe webhook not received

1. Verify webhook URL in Stripe dashboard
2. Check webhook signing secret matches STRIPE_WEBHOOK_SECRET
3. Verify event types are enabled
4. Check /ops/audit-logs for webhook event details

### K8s deployment stuck

1. Check pod logs: `kubectl logs -n orchestrator-prod pod-name`
2. Check resource limits/requests
3. Verify secrets are created: `kubectl get secrets -n orchestrator-prod`
4. Check ingress status: `kubectl describe ingress -n orchestrator-prod`

## Next Steps

- [ ] Set up monitoring (Prometheus, Grafana)
- [ ] Add rate limiting by IP/user
- [ ] Implement workflow-level access controls
- [ ] Add webhook integrations (Slack, email)
- [ ] Extend to custom LLM providers
- [ ] Add support for batch task processing
- [ ] Implement workflow templates marketplace
