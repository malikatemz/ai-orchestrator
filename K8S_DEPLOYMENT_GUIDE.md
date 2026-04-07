# Kubernetes Deployment Guide - AI Orchestrator

A comprehensive guide for deploying the AI Orchestrator platform to Kubernetes clusters with production-grade configurations, security, and observability.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Step-by-Step Deployment](#step-by-step-deployment)
4. [Verification](#verification)
5. [Health Checks](#health-checks)
6. [Troubleshooting](#troubleshooting)
7. [Next Steps](#next-steps)

---

## Prerequisites

Before deploying to Kubernetes, ensure you have:

### Required Tools

- **kubectl** (v1.24+): Kubernetes command-line tool
  ```bash
  # Install kubectl
  # macOS: brew install kubectl
  # Linux: curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  # Windows: choco install kubernetes-cli
  
  # Verify installation
  kubectl version --client
  ```

- **Helm** (v3.0+): Package manager for Kubernetes
  ```bash
  # Install Helm
  # macOS: brew install helm
  # Linux: curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
  
  # Verify installation
  helm version
  ```

- **Docker**: Container runtime (for building images)
  ```bash
  docker --version
  ```

### Infrastructure Requirements

- **Kubernetes Cluster** (v1.24+)
  - Minimum: 3 worker nodes with 2 CPU, 4GB RAM each
  - Recommended: 5+ nodes with 4 CPU, 8GB RAM for production
  - Supported cloud providers: AWS EKS, GCP GKE, Azure AKS, DigitalOcean DOKS

- **Storage Provisioner**
  - Default: Local volume provisioner or cloud provider's default storage class
  - Recommended: Fast NVMe for databases (AWS gp3, GCP pd-ssd, etc.)

- **Ingress Controller**
  - NGINX Ingress Controller (recommended)
  - Install: `helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx && helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace`

- **Certificate Manager**
  - Required for TLS/SSL certificates
  - Install: `helm repo add jetstack https://charts.jetstack.io && helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set installCRDs=true`

- **Monitoring Stack** (Optional but recommended)
  - Prometheus: Metrics collection
  - Grafana: Visualization
  - Install via Helm: `helm repo add prometheus-community https://prometheus-community.github.io/helm-charts`

### Network & DNS Requirements

- Custom domain: `yourdomain.com` and `api.yourdomain.com`
- DNS A records pointing to ingress load balancer
- Network connectivity: Worker nodes must reach the internet for pulling images

### Configuration Files

- Clone the repository:
  ```bash
  git clone https://github.com/yourusername/ai-orchestrator.git
  cd ai-orchestrator
  ```

---

## Quick Start

For rapid deployment in a test environment:

```bash
# 1. Create namespaces
kubectl apply -f k8s/day2-namespace.yaml

# 2. Create secrets
kubectl create secret generic ai-orchestrator-secrets \
  --from-literal=DATABASE_URL="postgresql://postgres:postgres@postgres-service:5432/ai_orchestrator" \
  --from-literal=REDIS_URL="redis://redis-service:6379/0" \
  --from-literal=JWT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  --from-literal=CELERY_BROKER_URL="redis://redis-service:6379/1" \
  --from-literal=CELERY_RESULT_BACKEND="redis://redis-service:6379/2" \
  --from-literal=POSTGRES_USER="postgres" \
  --from-literal=POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))')" \
  --namespace=ai-orchestrator-prod

# 3. Create ConfigMap and PVCs
kubectl apply -f k8s/day2-configmap.yaml
kubectl apply -f k8s/day2-service.yaml
kubectl apply -f k8s/day2-pvc.yaml

# 4. Deploy database and cache
kubectl apply -f k8s/day4-postgres-statefulset.yaml
kubectl apply -f k8s/day4-redis-statefulset.yaml

# 5. Deploy API and workers
kubectl apply -f k8s/day1-api-deployment.yaml
kubectl apply -f k8s/day1-worker-deployment.yaml

# 6. Deploy autoscaling
kubectl apply -f k8s/day1-hpa-cpu.yaml
# kubectl apply -f k8s/day1-hpa-keda.yaml  # Only if KEDA is installed

# 7. Deploy ingress and networking
kubectl apply -f k8s/day3-ingress.yaml
kubectl apply -f k8s/day3-network-policy.yaml

# 8. Deploy monitoring
kubectl apply -f k8s/day3-monitoring-config.yaml
```

Check deployment status:
```bash
kubectl get pods -n ai-orchestrator-prod
kubectl get svc -n ai-orchestrator-prod
kubectl get pvc -n ai-orchestrator-prod
```

---

## Step-by-Step Deployment

### Phase 1: Namespace & RBAC Setup

Create and configure isolated namespaces:

```bash
# Create namespaces with resource quotas
kubectl apply -f k8s/day2-namespace.yaml

# Verify namespaces
kubectl get namespaces -L environment,managed-by

# View resource quotas
kubectl describe resourcequota -n ai-orchestrator-dev
kubectl describe resourcequota -n ai-orchestrator-staging
kubectl describe resourcequota -n ai-orchestrator-prod
```

### Phase 2: Configure Secrets

**CRITICAL**: Never commit secrets to version control.

```bash
# Generate secure random values
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
DB_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
REDIS_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')

# Create secret in production namespace
kubectl create secret generic ai-orchestrator-secrets \
  --from-literal=DATABASE_URL="postgresql://postgres:${DB_PASSWORD}@postgres-service:5432/ai_orchestrator" \
  --from-literal=REDIS_URL="redis://:${REDIS_PASSWORD}@redis-service:6379/0" \
  --from-literal=JWT_SECRET_KEY="${JWT_SECRET}" \
  --from-literal=CELERY_BROKER_URL="redis://:${REDIS_PASSWORD}@redis-service:6379/1" \
  --from-literal=CELERY_RESULT_BACKEND="redis://:${REDIS_PASSWORD}@redis-service:6379/2" \
  --from-literal=POSTGRES_USER="postgres" \
  --from-literal=POSTGRES_PASSWORD="${DB_PASSWORD}" \
  --from-literal=REDIS_AUTH_PASSWORD="${REDIS_PASSWORD}" \
  --namespace=ai-orchestrator-prod

# Verify secret creation (doesn't show values)
kubectl get secret ai-orchestrator-secrets -n ai-orchestrator-prod
kubectl describe secret ai-orchestrator-secrets -n ai-orchestrator-prod
```

### Phase 3: Configure Application

```bash
# Apply ConfigMap
kubectl apply -f k8s/day2-configmap.yaml

# Verify ConfigMap
kubectl get configmap -n ai-orchestrator-prod
kubectl describe configmap ai-orchestrator-config -n ai-orchestrator-prod
```

### Phase 4: Create Storage & Networking

```bash
# Create PVCs for database, cache, and logs
kubectl apply -f k8s/day2-pvc.yaml

# Verify PVCs
kubectl get pvc -n ai-orchestrator-prod

# Create services
kubectl apply -f k8s/day2-service.yaml

# Verify services
kubectl get svc -n ai-orchestrator-prod
```

### Phase 5: Deploy Database

```bash
# Deploy PostgreSQL StatefulSet
kubectl apply -f k8s/day4-postgres-statefulset.yaml

# Wait for pod to be ready (can take 1-2 minutes)
kubectl wait --for=condition=ready pod \
  -l app=ai-orchestrator,component=database \
  -n ai-orchestrator-prod \
  --timeout=300s

# Verify deployment
kubectl describe pod postgres-0 -n ai-orchestrator-prod
kubectl logs postgres-0 -n ai-orchestrator-prod

# Test database connection
kubectl exec -it postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -d ai_orchestrator -c "SELECT version();"
```

### Phase 6: Deploy Cache (Redis)

```bash
# Deploy Redis StatefulSet
kubectl apply -f k8s/day4-redis-statefulset.yaml

# Wait for pod to be ready
kubectl wait --for=condition=ready pod \
  -l app=ai-orchestrator,component=cache \
  -n ai-orchestrator-prod \
  --timeout=300s

# Verify deployment
kubectl describe pod redis-0 -n ai-orchestrator-prod
kubectl logs redis-0 -n ai-orchestrator-prod

# Test cache connection
kubectl exec -it redis-0 -n ai-orchestrator-prod -- \
  redis-cli ping
```

### Phase 7: Deploy API Service

```bash
# Deploy API deployment
kubectl apply -f k8s/day1-api-deployment.yaml

# Wait for pods to be ready
kubectl rollout status deployment/ai-orchestrator-api -n ai-orchestrator-prod

# Verify deployment
kubectl get deployment ai-orchestrator-api -n ai-orchestrator-prod
kubectl describe deployment ai-orchestrator-api -n ai-orchestrator-prod

# Check pod logs
kubectl logs deployment/ai-orchestrator-api -n ai-orchestrator-prod -f
```

### Phase 8: Deploy Workers

```bash
# Deploy worker deployment
kubectl apply -f k8s/day1-worker-deployment.yaml

# Wait for pods to be ready
kubectl rollout status deployment/ai-orchestrator-worker -n ai-orchestrator-prod

# Verify deployment
kubectl get deployment ai-orchestrator-worker -n ai-orchestrator-prod

# Check pod logs
kubectl logs deployment/ai-orchestrator-worker -n ai-orchestrator-prod -f
```

### Phase 9: Configure Autoscaling

```bash
# Deploy HPA for CPU-based scaling
kubectl apply -f k8s/day1-hpa-cpu.yaml

# Verify HPA
kubectl get hpa -n ai-orchestrator-prod
kubectl describe hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod

# Optional: Deploy KEDA for queue-depth scaling (requires KEDA operator)
# kubectl apply -f k8s/day1-hpa-keda.yaml
```

### Phase 10: Configure Networking & Ingress

```bash
# Apply network policies
kubectl apply -f k8s/day3-network-policy.yaml

# Deploy ingress
kubectl apply -f k8s/day3-ingress.yaml

# Wait for ingress to be ready
kubectl wait --for=condition=ready ingress/ai-orchestrator-ingress \
  -n ai-orchestrator-prod \
  --timeout=300s

# Get ingress details
kubectl get ingress -n ai-orchestrator-prod
kubectl describe ingress ai-orchestrator-ingress -n ai-orchestrator-prod
```

### Phase 11: Configure Monitoring

```bash
# Deploy Prometheus and monitoring configs
kubectl apply -f k8s/day3-prometheus-config.yaml
kubectl apply -f k8s/day3-monitoring-config.yaml

# Verify prometheus deployment
kubectl get pods -n ai-orchestrator-prod -l app=prometheus
kubectl port-forward svc/prometheus 9090:9090 -n ai-orchestrator-prod &
# Access at: http://localhost:9090
```

### Phase 12: Configure Backups

```bash
# Deploy backup CronJob
kubectl apply -f k8s/day4-postgres-backup.yaml

# Verify backup schedule
kubectl get cronjob -n ai-orchestrator-prod
kubectl describe cronjob postgres-backup -n ai-orchestrator-prod
```

---

## Verification

### Complete Deployment Checklist

```bash
# Check all pods are running
kubectl get pods -n ai-orchestrator-prod
# Expected: All pods in Running status

# Check all services have endpoints
kubectl get svc -n ai-orchestrator-prod
# Expected: All services have endpoints (ENDPOINTS column populated)

# Check all PVCs are bound
kubectl get pvc -n ai-orchestrator-prod
# Expected: All PVCs in Bound status

# Check all deployments are ready
kubectl get deployments -n ai-orchestrator-prod
# Expected: READY column shows desired replicas

# Check ingress is ready
kubectl get ingress -n ai-orchestrator-prod
# Expected: Ingress has IP/hostname in ADDRESS column

# Check HPA is active
kubectl get hpa -n ai-orchestrator-prod
# Expected: TARGETS show current/target values
```

### API Health Checks

```bash
# Get API service IP
API_IP=$(kubectl get svc ai-orchestrator-api -n ai-orchestrator-prod -o jsonpath='{.spec.clusterIP}')

# Port forward to API
kubectl port-forward svc/ai-orchestrator-api 8000:8000 -n ai-orchestrator-prod &

# Test health endpoint
curl http://localhost:8000/health

# Test readiness endpoint
curl http://localhost:8000/health/ready

# Test metrics endpoint
curl http://localhost:8000/metrics
```

### Database Verification

```bash
# Connect to PostgreSQL
kubectl exec -it postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -d ai_orchestrator

# Sample SQL commands
SELECT version();
\dt  -- List tables
SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';
\q  -- Quit
```

### Redis Verification

```bash
# Connect to Redis
kubectl exec -it redis-0 -n ai-orchestrator-prod -- redis-cli

# Sample commands
PING
DBSIZE
INFO
QUIT
```

---

## Health Checks

The application includes comprehensive health checks:

### Liveness Probe
- **Endpoint**: `/health`
- **Interval**: 20 seconds
- **Purpose**: Restart pod if app is unresponsive

### Readiness Probe
- **Endpoint**: `/health/ready`
- **Interval**: 10 seconds
- **Purpose**: Remove from load balancer if unhealthy

### Startup Probe
- **Endpoint**: `/health`
- **Purpose**: Wait for app to fully start before other probes

View health check status:
```bash
kubectl get pods -n ai-orchestrator-prod -o custom-columns=\
  NAME:.metadata.name,\
  READY:.status.conditions[?(@.type=="Ready")].status,\
  RUNNING:.status.conditions[?(@.type=="ContainersReady")].status,\
  RESTARTS:.status.containerStatuses[0].restartCount

# Detailed health info
kubectl describe pod <pod-name> -n ai-orchestrator-prod
```

---

## Troubleshooting

### Pod Won't Start

```bash
# Check pod status
kubectl describe pod <pod-name> -n ai-orchestrator-prod

# Common issues:
# 1. ImagePullBackOff: Image not found
#    - Fix: Push image to registry or use local image

# 2. CrashLoopBackOff: Container crashes immediately
#    - Check logs: kubectl logs <pod-name> -n ai-orchestrator-prod
#    - Check resource limits
#    - Check environment variables

# 3. Pending: Insufficient resources
#    - Check node resources: kubectl describe nodes
#    - Check resource requests in manifests
```

### Service Not Accessible

```bash
# Check service endpoints
kubectl get endpoints -n ai-orchestrator-prod

# Check network policies
kubectl get networkpolicy -n ai-orchestrator-prod

# Test connectivity
kubectl run -it --rm debug --image=alpine --restart=Never -- \
  sh -c "apk add curl && curl http://ai-orchestrator-api:8000/health"
```

### Database Connection Issues

```bash
# Check database is running
kubectl get pod postgres-0 -n ai-orchestrator-prod

# Check logs
kubectl logs postgres-0 -n ai-orchestrator-prod

# Test connection
kubectl exec -it api-deployment-<hash> -n ai-orchestrator-prod -- \
  sh -c "psql $DATABASE_URL -c 'SELECT 1'"
```

### Resource Issues

```bash
# Check node resources
kubectl top nodes

# Check pod resource usage
kubectl top pods -n ai-orchestrator-prod

# Increase limits if needed
kubectl patch deployment ai-orchestrator-api -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"2Gi"}}}]}}}}'
```

---

## Next Steps

1. **Configure External Domain**
   - Update DNS records to point to ingress IP
   - Wait for DNS propagation (5-30 minutes)
   - Test: `curl https://api.yourdomain.com/health`

2. **Set Up Monitoring & Alerting**
   - Install Grafana dashboards
   - Configure AlertManager
   - Set up slack/email notifications

3. **Enable Backup & Disaster Recovery**
   - Configure S3/GCS for backups
   - Set up point-in-time recovery
   - Test restore procedures

4. **Configure CI/CD**
   - Set up automated deployments
   - Configure GitOps (ArgoCD)
   - Set up secret management (Vault/Sealed Secrets)

5. **Performance Tuning**
   - Monitor metrics in Prometheus
   - Adjust resource limits
   - Optimize database queries
   - Tune cache hit rates

---

## Additional Resources

- [Kubernetes Official Documentation](https://kubernetes.io/docs/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- [Cert-Manager](https://cert-manager.io/)
- [Prometheus Operator](https://prometheus-operator.dev/)
- [AI Orchestrator GitHub](https://github.com/yourusername/ai-orchestrator)

---

**Last Updated**: 2024
**Version**: 1.0.0
