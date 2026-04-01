# Troubleshooting & Production Monitoring Guide

Complete reference for diagnosing and resolving issues in development, staging, and production environments.

## Quick Diagnostics

### System Health Check Script

Create `backend/scripts/health_check.py`:

```python
#!/usr/bin/env python
"""System health check script"""

import asyncio
import sys
from app.config import get_settings
from app.database import engine
from sqlalchemy import text
import redis
import httpx

async def check_health():
    settings = get_settings()
    checks = {
        "database": False,
        "redis": False,
        "api_health": False,
        "openai_api": False,
    }
    
    # Database
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
        print("✓ Database: Connected")
    except Exception as e:
        print(f"✗ Database: {e}")
    
    # Redis
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
        checks["redis"] = True
        print("✓ Redis: Connected")
    except Exception as e:
        print(f"✗ Redis: {e}")
    
    # API Health
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.API_URL}/health")
            checks["api_health"] = response.status_code == 200
            print(f"✓ API Health: {response.status_code}")
    except Exception as e:
        print(f"✗ API Health: {e}")
    
    # OpenAI API
    try:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers=headers,
                timeout=5
            )
            checks["openai_api"] = response.status_code == 200
            print(f"✓ OpenAI API: {response.status_code}")
    except Exception as e:
        print(f"✗ OpenAI API: {e}")
    
    if all(checks.values()):
        print("\n✓ All systems operational")
        sys.exit(0)
    else:
        print(f"\n✗ {sum(1 for v in checks.values() if not v)} check(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(check_health())
```

Run:

```bash
cd backend
python scripts/health_check.py
```

---

## Common Issues & Solutions

### 1. Database Issues

#### Problem: "Could not connect to PostgreSQL"

**Symptoms:**
```
psycopg2.OperationalError: could not connect to server: Connection refused
Is the server running on host "localhost" (127.0.0.1) and accepting
TCP connections on port 5432?
```

**Diagnosis:**

```bash
# Check if PostgreSQL is running
psql -U postgres -c "SELECT 1" 2>&1

# If failed, start it
# macOS
brew services start postgresql@15

# Linux
sudo systemctl start postgresql

# Or with Docker
docker ps | grep postgres
docker start postgres
```

**Solutions:**

1. **Verify connection string in `.env`:**

```bash
echo $DATABASE_URL
# Should be: postgresql://user:pass@localhost:5432/dbname
```

2. **Test connection directly:**

```bash
psql $DATABASE_URL -c "SELECT 1"
```

3. **Check port:**

```bash
lsof -i :5432
# Should show postgres process

# If port conflicts, change to another
DATABASE_URL="postgresql://user:pass@localhost:5433/db"
```

4. **Reset database (development only):**

```bash
# Drop and recreate
dropdb orchestrator
createdb orchestrator

# Or via SQLAlchemy
alembic downgrade base
alembic upgrade head
```

---

#### Problem: "Alembic migration fails"

**Symptoms:**
```
FAILED: Can't drop constraint...
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedObject)
```

**Solutions:**

1. **Check for locked tables:**

```bash
psql orchestrator -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Kill blocking connections
SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
WHERE datname = 'orchestrator' AND pid <> pg_backend_pid();
```

2. **Downgrade to base state first:**

```bash
alembic downgrade base
alembic upgrade head
```

3. **Verify migration syntax:**

```bash
# Check latest migration file for errors
cat migrations/versions/latest_XXX_description.py

# Recreate migration
alembic revision --autogenerate -m "description"
```

---

#### Problem: "Database connection pool exhausted"

**Symptoms:**
```
sqlalchemy.pool.TimeoutError: 'The connection pool has exhausted'
QueuePool size: 5, Overflow: 5, Timeout: 5
```

**Solutions:**

1. **Increase pool size:**

```python
# backend/app/config.py
SQLALCHEMY_POOL_SIZE = 20  # Was 5
SQLALCHEMY_MAX_OVERFLOW = 10  # Was 10
```

2. **Check for connection leaks:**

```python
# Add logging to database session
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)
```

3. **Monitor active connections:**

```bash
psql orchestrator -c "SELECT count(*) FROM pg_stat_activity;"

# Per process
psql orchestrator -c "SELECT pid, usename, state FROM pg_stat_activity;"
```

---

### 2. Redis Issues

#### Problem: "Could not connect to Redis"

**Symptoms:**
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379.
Connection refused.
```

**Diagnosis:**

```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# If not:
# macOS
brew services start redis

# Linux
sudo systemctl start redis-server

# Docker
docker start redis
```

**Solutions:**

1. **Verify REDIS_URL:**

```bash
echo $REDIS_URL
# Should be: redis://localhost:6379 or redis://:password@localhost:6379
```

2. **Test Redis connection:**

```bash
redis-cli -u $REDIS_URL ping
```

3. **Check Redis memory:**

```bash
redis-cli info memory

# If nearly full, may be causing issues
redis-cli DBSIZE
redis-cli FLUSHDB  # Warning: clears all data
```

---

#### Problem: "Tasks not processing - Celery can't connect to Redis"

**Symptoms:**
```
[ERROR] Failed to connect to redis: ConnectionError
[ERROR] Consumer not running - unable to create worker
```

**Solutions:**

1. **Check Celery is configured correctly:**

```bash
cd backend

# Test broker connection
celery -A app.worker inspect active_queues
```

2. **Verify broker URL:**

```python
# backend/app/worker.py
app.conf.broker_url = settings.REDIS_URL
app.conf.result_backend = settings.REDIS_URL
```

3. **Restart worker cleanly:**

```bash
# Kill old worker processes
pkill -f "celery.*worker"

# Start fresh
celery -A app.worker worker --loglevel=info
```

4. **Check queue status:**

```bash
redis-cli

# View all queues
KEYS *

# Check specific queue length
LLEN celery

# View pending tasks
LRANGE celery 0 -1
```

---

### 3. API Issues

#### Problem: "API won't start - ImportError"

**Symptoms:**
```
ModuleNotFoundError: No module named 'app.agents'
```

**Solutions:**

1. **Verify package installed:**

```bash
pip list | grep orchestrator

# Reinstall
pip install -e .
```

2. **Check Python path:**

```bash
cd backend
PYTHONPATH=. python -c "from app.agents import router"
```

3. **Ensure __init__.py files exist:**

```bash
find backend/app -type d -exec touch {}/__init__.py \;
```

---

#### Problem: "Port already in use"

**Symptoms:**
```
OSError: [Errno 98] Address already in use
```

**Solutions:**

```bash
# Find process using port 8000
lsof -i :8000
# Output: COMMAND  PID  USER  FD  TYPE DEVICE SIZE/OFF NODE NAME
#         python  1234  user   10u  IPv4  12345  0t0  TCP

# Kill it
kill -9 1234

# Or use different port
uvicorn app.main:app --port 8001
```

---

#### Problem: "401 Unauthorized on API calls"

**Symptoms:**
```
{"detail": "Not authenticated"}
```

**Solutions:**

1. **Verify JWT token in request:**

```bash
curl -H "Authorization: Bearer $YOUR_TOKEN" http://localhost:8000/api/tasks
```

2. **Check token expiry:**

```python
# Decode token to see expiry
from app.auth.tokens import decode_token

payload = decode_token(token, "access")
print(payload["exp"])  # Unix timestamp

# Is current time before expiration?
import time
time.time() < payload["exp"]
```

3. **Generate new token for testing:**

```bash
# Use OAuth endpoints
curl http://localhost:8000/auth/google

# Or if testing, create token manually
python -c "
from app.auth.tokens import create_access_token
print(create_access_token('test-user-id'))
"
```

---

### 4. Worker Issues

#### Problem: "Tasks stuck in queue - not executing"

**Symptoms:**
```
Worker status: online=0, offline=0
Queued tasks: 42 (stuck)
```

**Solutions:**

1. **Check worker is running:**

```bash
# In another terminal
celery -A app.worker inspect active

# Should show worker registered
```

2. **Monitor queue:**

```bash
# Check tasks in queue
redis-cli LLEN celery
redis-cli LRANGE celery 0 10  # View first 10 tasks

# Clear stuck tasks (BE CAREFUL)
redis-cli FLUSHDB
```

3. **Worker logs:**

```bash
# Start worker in foreground with debug
celery -A app.worker worker --loglevel=debug

# Should show:
# [*] Connected to redis://localhost:6379
# [*] Pool max concurrency set to 4
```

4. **Restart worker:**

```bash
pkill -9 -f "celery.*worker"
celery -A app.worker worker --loglevel=info
```

---

#### Problem: "Task execution fails with provider timeout"

**Symptoms:**
```
[ERROR] Task execute_task_async failed: TimeoutError in provider execution
```

**Solutions:**

1. **Check provider API is accessible:**

```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Should return model list
```

2. **Verify API key is valid:**

```bash
# Check in worker logs
celery -A app.worker worker --loglevel=debug | grep "API key"
```

3. **Increase timeout in config:**

```python
# backend/app/config.py
PROVIDER_TIMEOUT_SECONDS = 60  # Was 30
```

4. **Check fallback chain is working:**

```bash
# Monitor logs during task execution
tail -f /tmp/celery.log | grep "fallback"

# Should show retry attempts
```

---

### 5. Billing Issues

#### Problem: "Stripe webhook not triggering"

**Symptoms:**
```
[WARNING] Webhook received but not processed
[ERROR] Unknown event type: customer.subscription.updated
```

**Solutions:**

1. **Verify webhook secret:**

```python
# backend/app/config.py
STRIPE_WEBHOOK_SECRET = "whsec_..."  # Must match Stripe CLI

# Check it's correct
stripe listen --forward-to localhost:8000/api/billing/webhooks/stripe
```

2. **Test webhook locally:**

```bash
# Listen for webhooks
stripe listen --forward-to localhost:8000/api/billing/webhooks/stripe

# Trigger test event
stripe trigger customer.subscription.created
```

3. **Check webhook payload:**

```python
# Add logging in routes_billing.py
@app.post("/api/billing/webhooks/stripe")
async def webhook(request: Request):
    payload = await request.body()
    print(f"Webhook payload: {payload}")  # Debug
    # Process...
```

---

#### Problem: "Customer hits rate limit but subscription shows active"

**Symptoms:**
```
BillingError: Rate limit exceeded (tasks: 1042/1000)
But subscription_status = "active"
```

**Solutions:**

1. **Reset usage for period:**

```bash
# Database
DELETE FROM usage_records 
WHERE org_id = 'org-xxx' 
AND created_at > NOW() - INTERVAL '1 month'
LIMIT 42;
```

2. **Check billing period calculates correctly:**

```python
from app.billing.service import get_usage_for_period

usage = get_usage_for_period(db, "org-xxx")
print(f"Usage this period: {usage}")

# Compare to plan limit
from app.billing.models import PLAN_CONFIGS
org = db.query(Organization).get("org-xxx")
limit = PLAN_CONFIGS[org.subscription_plan].task_limit_monthly
print(f"Limit: {limit}")
```

---

### 6. OAuth Issues

#### Problem: "Google OAuth redirect mismatch"

**Symptoms:**
```
Error: redirect_uri_mismatch
The redirect_uri parameter does not match the registered redirect URIs.
```

**Solutions:**

1. **Register all redirect URIs in Google Console:**

   - Dev: `http://localhost:3000/auth/google/callback`
   - Staging: `https://staging-app.example.com/auth/google/callback`
   - Prod: `https://app.example.com/auth/google/callback`

2. **Verify backend config matches:**

```python
# backend/app/config.py
GOOGLE_REDIRECT_URI = "http://localhost:3000/auth/google/callback"
```

3. **Check frontend redirect is correct:**

```javascript
// frontend/pages/auth/google.tsx
const redirectUri = `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/google/callback`;
```

---

#### Problem: "JWT token not working after OAuth"

**Symptoms:**
```
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/tasks
{"detail": "Invalid token"}
```

**Solutions:**

1. **Verify token format is correct:**

```bash
# Should be: Authorization: Bearer eyJ...

# Not: Authorization: $token

curl -H "Authorization: Bearer $YOUR_JWT" http://localhost:8000/api/tasks
```

2. **Check token isn't expired:**

```python
from app.auth.tokens import decode_token
import time

try:
    payload = decode_token(token, "access")
    if payload["exp"] < time.time():
        print("Token expired")
    else:
        print(f"Token valid until {payload['exp']}")
except Exception as e:
    print(f"Invalid token: {e}")
```

3. **Verify JWT_SECRET_KEY hasn't changed:**

```bash
# If changed, all tokens become invalid
echo $JWT_SECRET_KEY

# Should be consistent between API and worker
```

---

### 7. Kubernetes Issues

#### Problem: "Pods stuck in Pending"

**Symptoms:**
```
$ kubectl get pods -n orchestrator-prod

NAME                                READY   STATUS    RESTARTS   AGE
orchestrator-api-5d4d8f5d5f-abc     0/1     Pending   0          5m
```

**Diagnosis:**

```bash
# Describe pod for details
kubectl describe pod orchestrator-api-5d4d8f5d5f-abc -n orchestrator-prod

# Common issues:
# - Insufficient resources: "Insufficient memory"
# - PVC not bound: "PersistentVolumeClaim not found"
# - Image pull failed: "ImagePullBackOff"
```

**Solutions:**

1. **Check node resources:**

```bash
kubectl top nodes
kubectl describe nodes

# Add more nodes or increase instance size
```

2. **Check PVC binding:**

```bash
kubectl get pvc -n orchestrator-prod
# STATUS should be "Bound"

# If pending, create PV manually
```

3. **Fix image pull:**

```bash
kubectl get events -n orchestrator-prod | grep ImagePull

# Verify image exists in registry
docker pull ghcr.io/myorg/orchestrator-api:latest

# Check image pull secrets
kubectl get secrets -n orchestrator-prod
```

---

#### Problem: "CrashLoopBackOff"

**Symptoms:**
```
orchestrator-api-xxx   0/1     CrashLoopBackOff   4          2m
```

**Diagnosis:**

```bash
# Check logs
kubectl logs orchestrator-api-xxx -n orchestrator-prod --previous

# Common issues:
# - Missing environment variable
# - Database unreachable
# - Configuration error
```

**Solutions:**

1. **Check logs for errors:**

```bash
kubectl logs -f deployment/orchestrator-api -n orchestrator-prod
```

2. **Verify secrets are mounted:**

```bash
kubectl exec orchestrator-api-xxx -n orchestrator-prod -- env | grep DATABASE

# Should show DATABASE_URL=/var/run/secrets/database_url
```

3. **Check health endpoint:**

```bash
kubectl port-forward pod/orchestrator-api-xxx 8000:8000 -n orchestrator-prod

# In another terminal
curl http://localhost:8000/health

# Should return {"status": "ok"}
```

---

#### Problem: "Ingress not routing traffic"

**Symptoms:**
```
curl https://app.example.com  → 502 Bad Gateway
curl https://api.example.com  → 404
```

**Diagnosis:**

```bash
# Check ingress
kubectl describe ingress orchestrator-ingress -n orchestrator-prod

# Check backend service
kubectl get svc -n orchestrator-prod
# Both app and api services should exist

# Check endpoints
kubectl get endpoints -n orchestrator-prod
# Should show IP:port for each service
```

**Solutions:**

1. **Verify DNS resolution:**

```bash
# From your machine
nslookup app.example.com

# Should return Ingress IP

# Update DNS if needed
```

2. **Check TLS certificate:**

```bash
kubectl describe certificate orchestrator-tls -n orchestrator-prod

# Status should be "True"
# If pending, check cert-manager logs

kubectl logs -f deployment/cert-manager -n cert-manager
```

3. **Test backend directly via port-forward:**

```bash
kubectl port-forward svc/orchestrator-api 8000:8000 -n orchestrator-prod

# In another terminal
curl http://localhost:8000/health
```

---

## Monitoring Dashboards

### Create Monitoring Dashboard

Install Prometheus + Grafana:

```bash
# Add Prometheus Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack (includes Prometheus + Grafana)
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace
```

---

### Key Metrics to Monitor

```yaml
# API Metrics
http_requests_total
http_requests_duration_seconds
instance_http_requests_total

# Database Metrics
pg_stat_database_tup_fetched
pg_stat_database_tup_inserted
db_connection_pool_size

# Worker Metrics
celery_task_total
celery_task_duration_seconds
celery_queue_length

# Provider Metrics
provider_success_rate
provider_avg_latency_ms
provider_cost_usd_total

# Billing Metrics
org_tasks_used_total
org_subscription_status

# System Metrics
node_memory_MemAvailable_bytes
node_cpu_seconds_total
kubernetes_pod_cpu_node_allocatable
```

---

### Log Aggregation

Setup centralized logging:

```yaml
# docker-compose.yml addition
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:8.0.0
  environment:
    - discovery.type=single-node
  ports:
    - "9200:9200"

kibana:
  image: docker.elastic.co/kibana/kibana:8.0.0
  ports:
    - "5601:5601"
```

Send logs from API:

```python
# backend/app/config.py
import structlog
from pythonjsonlogger import jsonlogger

structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ],
)

# Logs will be JSON-formatted, easy to parse
logger.info("task_completed", task_id="123", duration_ms=1234)
# Output: {"event": "task_completed", "task_id": "123", "duration_ms": 1234}
```

---

## Alert Rules

Create alert rules for critical issues:

```yaml
# prometheus-rules.yaml
groups:
  - name: orchestrator
    interval: 30s
    rules:
      - alert: APIHighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "API error rate > 5%"
      
      - alert: WorkerTaskQueue
        expr: celery_queue_length > 1000
        for: 10m
        annotations:
          summary: "{{ $value }} tasks stuck in queue"
      
      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        annotations:
          summary: "Database unreachable"
      
      - alert: OrgExceededBillingQuota
        expr: org_tasks_used_total > org_task_limit
        annotations:
          summary: "Organization {{ $labels.org_id }} exceeded quota"
```

---

## Performance Tuning Checklist

- [ ] Database query optimization (add indexes for common filters)
- [ ] API connection pooling configured
- [ ] Redis memory management (eviction policy set)
- [ ] Worker concurrency tuned for available CPU
- [ ] HPA min/max replicas optimized
- [ ] Request timeout configured per provider
- [ ] Caching strategy for frequently accessed data
- [ ] Logging level optimized for production (WARNING+)
- [ ] Unused endpoints removed or deprecated
- [ ] Database slow query log enabled

---

## Escalation Path

1. **Level 1 - Health Checks:** Run `health_check.py` script
2. **Level 2 - Service Logs:** Check service-specific logs
3. **Level 3 - Metrics:** Review Prometheus/Grafana dashboards
4. **Level 4 - Database:** Check connection pool, query performance
5. **Level 5 - Infrastructure:** Check K8s node status, network
6. **Level 6 - Incident Post-Mortem:** Document root cause and prevention

---

## Support Resources

- [Fastapi Docs](https://fastapi.tiangolo.com/)
- [Celery Docs](https://docs.celeryproject.org/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Kubernetes Docs](https://kubernetes.io/docs/)
- [Stripe API Docs](https://stripe.com/docs/api)
- [OpenAI API Status](https://status.openai.com/)
