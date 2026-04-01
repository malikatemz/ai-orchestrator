# Kubernetes & Helm Deployment Guide

Complete guide for deploying AI Orchestration Platform to production Kubernetes cluster.

## Prerequisites

- Kubernetes cluster (1.24+) with at least 3 worker nodes
- `kubectl` configured with cluster access
- Helm 3.x installed
- Docker registry access (ghcr.io, Docker Hub, or private)
- Optional: sealed-secrets controller for secret encryption
- Optional: cert-manager for TLS certificates
- Optional: KEDA for queue-based autoscaling

## Architecture

### Components

1. **Namespace:** `orchestrator-prod` (isolated from other workloads)
2. **Database:** PostgreSQL 15 (StatefulSet, persistent storage)
3. **Cache:** Redis 7 (StatefulSet, persistent storage)
4. **API:** FastAPI (Deployment, 2-10 replicas, CPU-based HPA)
5. **Worker:** Celery (Deployment, 2-20 replicas, KEDA queue-depth scaling)
6. **Frontend:** Next.js (Deployment, 2-5 replicas)
7. **Ingress:** Nginx with TLS via cert-manager

### Networking

```
Internet
    │
    ▼
Nginx Ingress (TLS)
    ├─ {APP_DOMAIN} ──▶ Frontend Service (3000)
    └─ {API_DOMAIN} ──▶ API Service (8000)
                           │
                      ┌────┴────┐
                      ▼         ▼
                    Redis   PostgreSQL
```

## 1. Prepare Docker Images

### Build Images

```bash
cd /path/to/orchestrator

# API
docker build -t ghcr.io/myorg/orchestrator-api:v1.0.0 -f backend/Dockerfile backend/

# Worker
docker build -t ghcr.io/myorg/orchestrator-worker:v1.0.0 -f backend/Dockerfile.worker backend/

# Frontend
docker build -t ghcr.io/myorg/orchestrator-frontend:v1.0.0 frontend/
```

### Push to Registry

```bash
docker push ghcr.io/myorg/orchestrator-api:v1.0.0
docker push ghcr.io/myorg/orchestrator-worker:v1.0.0
docker push ghcr.io/myorg/orchestrator-frontend:v1.0.0
```

## 2. Prepare Secrets

### Option A: Sealed Secrets (Recommended for Git)

Install sealed-secrets controller:

```bash
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.18.0/controller.yaml
```

Create and seal secrets:

```bash
# Create secret file
cat > secrets.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: orchestrator-secrets
  namespace: orchestrator-prod
type: Opaque
stringData:
  DATABASE_URL: postgresql://orchestrator:STRONG_PASSWORD@postgres:5432/orchestrator
  REDIS_URL: redis://redis:6379
  OPENAI_API_KEY: sk-...
  ANTHROPIC_API_KEY: sk-ant-...
  MISTRAL_API_KEY: ...
  STRIPE_SECRET_KEY: sk_live_...
  JWT_SECRET_KEY: $(openssl rand -hex 32)
  GOOGLE_CLIENT_ID: ...
  GOOGLE_CLIENT_SECRET: ...
  GITHUB_CLIENT_ID: ...
  GITHUB_CLIENT_SECRET: ...
EOF

# Seal it
kubeseal -f secrets.yaml -w secrets.sealed.yaml

# Commit to git
git add secrets.sealed.yaml
```

Deploy sealed secret:

```bash
kubectl apply -f secrets.sealed.yaml
```

### Option B: Manual Secret (Dev Only)

```bash
kubectl create secret generic orchestrator-secrets \
  -n orchestrator-prod \
  --from-literal=DATABASE_URL="postgresql://..." \
  --from-literal=REDIS_URL="redis://..." \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --from-literal=STRIPE_SECRET_KEY="sk_live_..." \
  --from-literal=JWT_SECRET_KEY="$(openssl rand -hex 32)" \
  ...
```

## 3. Deploy with Kubectl (Direct Manifests)

### Create Namespace & RBAC

```bash
kubectl apply -f k8s/00-namespace-rbac.yaml
```

Verify:

```bash
kubectl get namespace orchestrator-prod
kubectl get serviceaccounts -n orchestrator-prod
```

### Deploy Database & Cache

```bash
kubectl apply -f k8s/01-database-redis.yaml
```

Wait for StatefulSets to be ready:

```bash
kubectl wait --for=condition=ready pod \
  -l app=postgres \
  -n orchestrator-prod \
  --timeout=300s

kubectl wait --for=condition=ready pod \
  -l app=redis \
  -n orchestrator-prod \
  --timeout=300s
```

### Run Database Migrations

```bash
# Find a pod to execute migrations
API_POD=$(kubectl get pods -n orchestrator-prod -l app=orchestrator-api -o jsonpath='{.items[0].metadata.name}')

kubectl exec -it $API_POD -n orchestrator-prod -- \
  alembic upgrade head
```

### Deploy API, Worker, Frontend

```bash
kubectl apply -f k8s/02-api-deployment.yaml
kubectl apply -f k8s/03-worker-deployment.yaml
kubectl apply -f k8s/04-frontend-deployment.yaml
```

Wait for rollout:

```bash
kubectl rollout status deployment/orchestrator-api -n orchestrator-prod --timeout=5m
kubectl rollout status deployment/orchestrator-worker -n orchestrator-prod --timeout=5m
kubectl rollout status deployment/orchestrator-frontend -n orchestrator-prod --timeout=5m
```

### Deploy Autoscaling

```bash
# CPU-based
kubectl apply -f k8s/05-hpa.yaml

# Queue-depth-based (requires KEDA)
kubectl apply -f k8s/08-keda-scaler.yaml
```

### Deploy Ingress & TLS

```bash
# If cert-manager not installed:
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Apply ingress
kubectl apply -f k8s/06-ingress.yaml
```

Get Ingress IP:

```bash
kubectl get ingress -n orchestrator-prod
# Update your DNS records to point {APP_DOMAIN} and {API_DOMAIN} to the Ingress IP
```

## 4. Deploy with Helm (Recommended)

### Install Helm Chart

Create `values-prod.yaml`:

```yaml
global:
  domain: "example.com"
  appDomain: "app.example.com"
  apiDomain: "api.example.com"
  acmeEmail: "ops@example.com"

namespace:
  create: true
  name: orchestrator-prod

images:
  registry: ghcr.io
  org: myorg
  api:
    repository: orchestrator-api
    tag: v1.0.0
  worker:
    repository: orchestrator-worker
    tag: v1.0.0
  frontend:
    repository: orchestrator-frontend
    tag: v1.0.0

api:
  replicas: 3
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 1Gi

worker:
  replicas: 3
  resources:
    requests:
      cpu: 1000m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 2Gi

autoscaling:
  api:
    maxReplicas: 10
  worker:
    maxReplicas: 20
  frontend:
    maxReplicas: 5

postgres:
  storage: 20Gi

redis:
  storage: 10Gi

ingress:
  enabled: true
  tlsEnabled: true
  certManager: true
```

Install:

```bash
helm repo add orchestrator ./helm
helm repo update

helm install orchestrator ./helm/orchestrator \
  -f values-prod.yaml \
  -n orchestrator-prod \
  --create-namespace \
  --wait
```

Verify:

```bash
helm status orchestrator -n orchestrator-prod
kubectl get all -n orchestrator-prod
```

## 5. Verify Deployment

### Check Pods

```bash
kubectl get pods -n orchestrator-prod -o wide
```

All pods should be `Running` and `Ready`.

### Check Services

```bash
kubectl get svc -n orchestrator-prod
```

- `orchestrator-api`: ClusterIP (internal)
- `orchestrator-worker`: None (headless)
- `orchestrator-frontend`: ClusterIP (internal)
- `postgres`, `redis`: ClusterIP + headless
- `orchestrator-ingress`: LoadBalancer or ExternalIP

### Test API Health

```bash
# Port-forward for testing
kubectl port-forward svc/orchestrator-api 8000:8000 -n orchestrator-prod &

# In another terminal
curl http://localhost:8000/health
# Should return: {"status": "ok", "database": "connected", ...}
```

### Check Logs

```bash
# API logs
kubectl logs -f deployment/orchestrator-api -n orchestrator-prod

# Worker logs
kubectl logs -f deployment/orchestrator-worker -n orchestrator-prod

# Frontend logs
kubectl logs -f deployment/orchestrator-frontend -n orchestrator-prod
```

### Monitor Autoscaling

```bash
# Watch HPA
kubectl get hpa -n orchestrator-prod -w

# Watch pod growth under load
kubectl get pods -n orchestrator-prod -w
```

## 6. Upgrade Deployment

### Update Images

```bash
# Rebuild and push
docker build -t ghcr.io/myorg/orchestrator-api:v1.0.1 -f backend/Dockerfile backend/
docker push ghcr.io/myorg/orchestrator-api:v1.0.1

# Update deployment
kubectl set image deployment/orchestrator-api \
  api=ghcr.io/myorg/orchestrator-api:v1.0.1 \
  -n orchestrator-prod

# Or use Helm
helm upgrade orchestrator ./helm/orchestrator \
  -f values-prod.yaml \
  --set images.api.tag=v1.0.1
```

### Database Migrations

```bash
# Helm: Specify migration hook
helm upgrade orchestrator ./helm/orchestrator \
  --hooks --wait
```

Or manually:

```bash
API_POD=$(kubectl get pods -n orchestrator-prod -l app=orchestrator-api -o jsonpath='{.items[0].metadata.name}')

kubectl exec $API_POD -n orchestrator-prod -- alembic upgrade head
```

## 7. Scaling

### Manual Scaling

```bash
# Scale API to 5 replicas
kubectl scale deployment orchestrator-api --replicas=5 -n orchestrator-prod

# Scale workers to 10
kubectl scale deployment orchestrator-worker --replicas=10 -n orchestrator-prod
```

### Automatic Scaling

CPU-based HPA (already deployed):

```yaml
minReplicas: 2
maxReplicas: 10
targetCPUUtilizationPercentage: 60
```

Queue-depth KEDA scaler (Redis list):

```yaml
listName: celery
listLength: "50"  # Scale when queue > 50 items
```

Monitor scaling:

```bash
watch kubectl get hpa -n orchestrator-prod
```

## 8. Monitoring & Logging

### Metrics

```bash
# Get resource usage
kubectl top pods -n orchestrator-prod
kubectl top nodes
```

### Logs

```bash
# Real-time logs
kubectl logs -f deployment/orchestrator-api -n orchestrator-prod --all-containers=true

# From past 1 hour
kubectl logs deployment/orchestrator-api -n orchestrator-prod --since=1h

# From specific pod
kubectl logs pod-name -n orchestrator-prod
```

### Events

```bash
kubectl get events -n orchestrator-prod --sort-by='.lastTimestamp'
```

## 9. Backup & Recovery

### Backup Database

```bash
# Using kubectl
kubectl exec -it $(kubectl get pods -l app=postgres -o jsonpath='{.items[0].metadata.name}') \
  -n orchestrator-prod \
  -- pg_dump -U orchestrator orchestrator > backup.sql

# Upload to S3/backup service
```

### Restore Database

```bash
psql -U orchestrator orchestrator < backup.sql
```

### Backup Redis

```bash
kubectl exec -it $(kubectl get pods -l app=redis -o jsonpath='{.items[0].metadata.name}') \
  -n orchestrator-prod \
  -- redis-cli BGSAVE
```

## 10. Troubleshooting

### Pods stuck in Pending

```bash
kubectl describe pod pod-name -n orchestrator-prod
# Check: Resource limits, node capacity, PVC binding
```

### CrashLoopBackOff

```bash
kubectl logs pod-name -n orchestrator-prod --previous
# Check: Environment variables, secrets, database connectivity
```

### Ingress not working

```bash
kubectl describe ingress orchestrator-ingress -n orchestrator-prod
# Check: DNS resolution, cert status, backend connectivity
```

### Database connections failing

```bash
kubectl exec -it postgres-pod-name -n orchestrator-prod -- psql -U orchestrator
# Verify: Database exists, user permissions
```

### Workers not processing tasks

```bash
# Check queue
kubectl exec -it redis-pod-name -n orchestrator-prod -- redis-cli LLEN celery

# Check worker logs
kubectl logs -f deployment/orchestrator-worker -n orchestrator-prod

# Restart workers
kubectl rollout restart deployment/orchestrator-worker -n orchestrator-prod
```

## 11. Security Best Practices

- [ ] Use sealed-secrets for all sensitive data
- [ ] Enable RBAC (already configured)
- [ ] Use Network Policies to restrict traffic
- [ ] Enable Pod Security Policies / Pod Security Standards
- [ ] Regular image scanning for vulnerabilities
- [ ] Implement resource quotas per namespace
- [ ] Enable audit logging
- [ ] Regular backup testing
- [ ] Rotate secrets periodically
- [ ] Use private container registry with authentication

## 12. Performance Tuning

### Resource Requests & Limits

Adjust in Helm values based on actual usage:

```yaml
api:
  resources:
    requests:
      cpu: 500m      # Reservation
      memory: 512Mi
    limits:
      cpu: 2000m    # Ceiling
      memory: 2Gi
```

### HPA Thresholds

```yaml
autoscaling:
  api:
    targetCPU: 50  # More aggressive: scale earlier
```

### Database Connection Pool

```yaml
DATABASE_POOL_SIZE: 20   # Max connections
DATABASE_MAX_OVERFLOW: 10  # Additional when pool exhausted
```

## Quick Reference

```bash
# Deploy
kubectl apply -f k8s/

# Check status
kubectl get all -n orchestrator-prod

# Logs
kubectl logs -f deployment/orchestrator-api -n orchestrator-prod

# Scale
kubectl scale deployment/orchestrator-api --replicas=5 -n orchestrator-prod

# Upgrade
helm upgrade orchestrator ./helm/orchestrator -f values.yaml

# Delete
helm uninstall orchestrator -n orchestrator-prod
kubectl delete namespace orchestrator-prod
```

## Support

For issues:

1. Check pod logs: `kubectl logs <pod> -n orchestrator-prod`
2. Check events: `kubectl describe pod <pod> -n orchestrator-prod`
3. Check resource usage: `kubectl top pods -n orchestrator-prod`
4. Check Sentry dashboard for application errors
5. Check audit logs: `GET /ops/audit-logs`
