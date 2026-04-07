# Kubernetes Operations Guide - AI Orchestrator

Operational procedures and best practices for running AI Orchestrator in Kubernetes production environments.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Scaling Operations](#scaling-operations)
3. [Updates & Maintenance](#updates--maintenance)
4. [Performance Tuning](#performance-tuning)
5. [Troubleshooting](#troubleshooting)

---

## Daily Operations

### Monitoring Pod Status

```bash
# View all pods in production namespace
kubectl get pods -n ai-orchestrator-prod

# View pods with more details
kubectl get pods -n ai-orchestrator-prod -o wide

# Watch pods in real-time
kubectl get pods -n ai-orchestrator-prod --watch

# View pod details
kubectl describe pod <pod-name> -n ai-orchestrator-prod

# View pod labels
kubectl get pods -n ai-orchestrator-prod --show-labels
```

### Viewing Logs

```bash
# View recent logs
kubectl logs <pod-name> -n ai-orchestrator-prod

# View logs with timestamps
kubectl logs <pod-name> -n ai-orchestrator-prod --timestamps=true

# Follow logs in real-time
kubectl logs <pod-name> -n ai-orchestrator-prod -f

# View logs from all pods in deployment
kubectl logs deployment/ai-orchestrator-api -n ai-orchestrator-prod -f

# View logs from previous crashed container
kubectl logs <pod-name> -n ai-orchestrator-prod --previous

# View logs with tail limit
kubectl logs <pod-name> -n ai-orchestrator-prod --tail=100

# Export logs to file
kubectl logs <pod-name> -n ai-orchestrator-prod > logs.txt
```

### Accessing Containers

```bash
# Execute command in pod
kubectl exec -it <pod-name> -n ai-orchestrator-prod -- <command>

# Open shell in pod
kubectl exec -it <pod-name> -n ai-orchestrator-prod -- /bin/sh

# Copy files to/from pod
kubectl cp <pod-name>:/path/to/file ./local/path -n ai-orchestrator-prod
kubectl cp ./local/file <pod-name>:/path/to/destination -n ai-orchestrator-prod

# Run temporary debug pod
kubectl run -it --rm debug --image=alpine --restart=Never -n ai-orchestrator-prod -- sh
```

### Common kubectl Commands

```bash
# Get resources
kubectl get pods -n ai-orchestrator-prod
kubectl get svc -n ai-orchestrator-prod
kubectl get pvc -n ai-orchestrator-prod
kubectl get deploy -n ai-orchestrator-prod
kubectl get statefulsets -n ai-orchestrator-prod

# Describe resources (detailed information)
kubectl describe pod <pod-name> -n ai-orchestrator-prod
kubectl describe svc <service-name> -n ai-orchestrator-prod
kubectl describe deploy <deployment-name> -n ai-orchestrator-prod

# Delete resources
kubectl delete pod <pod-name> -n ai-orchestrator-prod
kubectl delete deployment <deployment-name> -n ai-orchestrator-prod

# Apply manifests
kubectl apply -f manifest.yaml
kubectl apply -f k8s/

# Rollout commands
kubectl rollout status deployment/ai-orchestrator-api -n ai-orchestrator-prod
kubectl rollout history deployment/ai-orchestrator-api -n ai-orchestrator-prod
kubectl rollout undo deployment/ai-orchestrator-api -n ai-orchestrator-prod

# Port forwarding
kubectl port-forward svc/ai-orchestrator-api 8000:8000 -n ai-orchestrator-prod
kubectl port-forward pod/<pod-name> 8000:8000 -n ai-orchestrator-prod
```

### Database Operations

```bash
# Connect to PostgreSQL
kubectl exec -it postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -d ai_orchestrator

# Backup database
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  pg_dump -U postgres ai_orchestrator | gzip > backup.sql.gz

# Restore database
gunzip -c backup.sql.gz | kubectl exec -i postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator

# Database size
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT pg_size_pretty(pg_database_size('ai_orchestrator'));"

# Table sizes
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Query activity
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT * FROM pg_stat_activity;"
```

### Cache (Redis) Operations

```bash
# Connect to Redis
kubectl exec -it redis-0 -n ai-orchestrator-prod -- redis-cli

# Check memory usage
kubectl exec redis-0 -n ai-orchestrator-prod -- redis-cli INFO memory

# Check database sizes
kubectl exec redis-0 -n ai-orchestrator-prod -- redis-cli INFO keyspace

# Flush database (DANGEROUS)
# kubectl exec redis-0 -n ai-orchestrator-prod -- redis-cli FLUSHDB

# Check connected clients
kubectl exec redis-0 -n ai-orchestrator-prod -- redis-cli INFO clients
```

---

## Scaling Operations

### Manual Pod Scaling

```bash
# Scale deployment to specific number of replicas
kubectl scale deployment ai-orchestrator-api --replicas=3 -n ai-orchestrator-prod

# Scale worker deployment
kubectl scale deployment ai-orchestrator-worker --replicas=5 -n ai-orchestrator-prod

# Get current replica count
kubectl get deployment ai-orchestrator-api -n ai-orchestrator-prod -o jsonpath='{.spec.replicas}'
```

### HPA (Horizontal Pod Autoscaler) Monitoring

```bash
# View HPA status
kubectl get hpa -n ai-orchestrator-prod

# Detailed HPA status
kubectl describe hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod

# Watch HPA activity
kubectl get hpa -n ai-orchestrator-prod --watch

# Edit HPA configuration
kubectl edit hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod

# View HPA events
kubectl get events -n ai-orchestrator-prod --field-selector involvedObject.name=ai-orchestrator-api-hpa
```

### Resource Monitoring

```bash
# View node resources
kubectl top nodes

# View pod resources
kubectl top pods -n ai-orchestrator-prod

# View resource requests vs usage
kubectl get pods -n ai-orchestrator-prod -o custom-columns=\
  NAME:.metadata.name,\
  CPU_REQ:.spec.containers[0].resources.requests.cpu,\
  CPU_LIM:.spec.containers[0].resources.limits.cpu,\
  MEM_REQ:.spec.containers[0].resources.requests.memory,\
  MEM_LIM:.spec.containers[0].resources.limits.memory

# Check resource quotas
kubectl describe resourcequota -n ai-orchestrator-prod
```

### Adjusting Resource Limits

```bash
# Patch deployment with new limits
kubectl patch deployment ai-orchestrator-api -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"2Gi","cpu":"2000m"}}}]}}}}'

# Edit deployment directly
kubectl edit deployment ai-orchestrator-api -n ai-orchestrator-prod

# Update statefulset memory
kubectl patch statefulset postgres -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"postgres","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
```

---

## Updates & Maintenance

### Rolling Updates

```bash
# Update deployment image
kubectl set image deployment/ai-orchestrator-api \
  api=ai-orchestrator:v1.1.0 \
  -n ai-orchestrator-prod

# Check rollout status
kubectl rollout status deployment/ai-orchestrator-api -n ai-orchestrator-prod

# Pause rollout
kubectl rollout pause deployment/ai-orchestrator-api -n ai-orchestrator-prod

# Resume rollout
kubectl rollout resume deployment/ai-orchestrator-api -n ai-orchestrator-prod

# Undo rollout
kubectl rollout undo deployment/ai-orchestrator-api -n ai-orchestrator-prod

# View rollout history
kubectl rollout history deployment/ai-orchestrator-api -n ai-orchestrator-prod

# Rollback to specific revision
kubectl rollout undo deployment/ai-orchestrator-api --to-revision=2 -n ai-orchestrator-prod
```

### Zero-Downtime Deployments

```bash
# Update deployment with rolling strategy (already configured in manifests)
# The deployment uses RollingUpdate with maxSurge: 1, maxUnavailable: 0

# Check rolling update configuration
kubectl get deployment ai-orchestrator-api -n ai-orchestrator-prod -o yaml | grep -A 5 "strategy:"

# Monitor rolling update
kubectl get pods -n ai-orchestrator-prod --watch

# Force recreation of pods (triggers rolling update)
kubectl rollout restart deployment/ai-orchestrator-api -n ai-orchestrator-prod
```

### Database Migrations

```bash
# Run migrations before deployment
kubectl run -it --rm migrate \
  --image=ai-orchestrator:latest \
  --restart=Never \
  -n ai-orchestrator-prod \
  -- alembic upgrade head

# Check migration history
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "SELECT * FROM alembic_version;"

# Rollback database to previous version
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "DELETE FROM alembic_version;"
```

### Configuration Updates

```bash
# Update ConfigMap
kubectl edit configmap ai-orchestrator-config -n ai-orchestrator-prod

# Apply updated ConfigMap
kubectl apply -f k8s/day2-configmap.yaml

# Restart pods to pick up new config
kubectl rollout restart deployment/ai-orchestrator-api -n ai-orchestrator-prod

# Verify ConfigMap was updated
kubectl describe configmap ai-orchestrator-config -n ai-orchestrator-prod
```

### Secret Rotation

```bash
# View current secret
kubectl get secret ai-orchestrator-secrets -n ai-orchestrator-prod -o yaml

# Update secret
kubectl create secret generic ai-orchestrator-secrets \
  --from-literal=JWT_SECRET_KEY="new-secret-key" \
  --dry-run=client -o yaml | kubectl apply -f -

# Verify secret update
kubectl describe secret ai-orchestrator-secrets -n ai-orchestrator-prod

# Restart pods to use new secret
kubectl rollout restart deployment/ai-orchestrator-api -n ai-orchestrator-prod

# Verify pods restarted
kubectl get pods -n ai-orchestrator-prod
```

---

## Performance Tuning

### Database Connection Pool Tuning

```bash
# Check current connection count
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT COUNT(*) as active_connections FROM pg_stat_activity;"

# Adjust pool size in ConfigMap (DATABASE_POOL_SIZE)
kubectl edit configmap ai-orchestrator-config -n ai-orchestrator-prod

# Recommended values:
# - Single pod: 5-10
# - Moderate load: 10-20
# - High load: 20-30
```

### Cache Optimization

```bash
# Check Redis memory usage
kubectl exec redis-0 -n ai-orchestrator-prod -- redis-cli INFO memory

# Check cache hit rate
kubectl exec redis-0 -n ai-orchestrator-prod -- redis-cli INFO stats

# Typical metrics to monitor:
# - Used memory: Should be < 80% of maxmemory
# - Evicted keys: Indicates memory pressure
# - Keyspace hits/misses: Hit rate should be > 90%
```

### Worker Concurrency Tuning

```bash
# Check current configuration
kubectl describe configmap ai-orchestrator-config -n ai-orchestrator-prod | grep -i worker

# Adjust worker concurrency in ConfigMap
kubectl edit configmap ai-orchestrator-config -n ai-orchestrator-prod

# Update WORKER_CONCURRENCY and WORKER_PREFETCH_MULTIPLIER
# Recommended:
# - CPU-bound tasks: concurrency = number of cores
# - I/O-bound tasks: concurrency = cores * 2-4
```

### Query Performance

```bash
# Enable slow query log
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "ALTER SYSTEM SET log_min_duration_statement = 1000;"

# Check slow queries
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Create index on slow queries (example)
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "CREATE INDEX idx_users_email ON users(email);"
```

---

## Troubleshooting

### Pod Troubleshooting

```bash
# Check pod status
kubectl describe pod <pod-name> -n ai-orchestrator-prod

# View pod events
kubectl get events -n ai-orchestrator-prod --field-selector involvedObject.name=<pod-name>

# Check resource usage
kubectl top pod <pod-name> -n ai-orchestrator-prod

# View pod startup logs
kubectl logs <pod-name> -n ai-orchestrator-prod

# Check environment variables
kubectl exec <pod-name> -n ai-orchestrator-prod -- env | grep -i database
```

### Connectivity Issues

```bash
# Test DNS resolution
kubectl exec <pod-name> -n ai-orchestrator-prod -- \
  nslookup postgres-service

# Test network connectivity
kubectl exec <pod-name> -n ai-orchestrator-prod -- \
  nc -zv postgres-service 5432

# Check network policies
kubectl get networkpolicy -n ai-orchestrator-prod
kubectl describe networkpolicy allow-api-to-postgres -n ai-orchestrator-prod

# Test from debug pod
kubectl run -it --rm debug --image=alpine --restart=Never -n ai-orchestrator-prod -- sh
# Inside pod: apk add curl netcat-openbsd && nc -zv postgres-service 5432
```

### Disk Space Issues

```bash
# Check PVC usage
kubectl exec postgres-0 -n ai-orchestrator-prod -- df -h /var/lib/postgresql/data

# Check available PVs
kubectl get pv

# Resize PVC (if storage class supports expansion)
kubectl patch pvc postgres-pvc -n ai-orchestrator-prod \
  -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'

# Database cleanup (if space is critical)
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "VACUUM ANALYZE;"
```

### Memory Pressure

```bash
# Check node memory
kubectl top nodes

# Check pod memory
kubectl top pods -n ai-orchestrator-prod

# Identify high memory consumers
kubectl get pods -n ai-orchestrator-prod --sort-by=.spec.containers[0].resources.requests.memory

# Increase pod memory limits
kubectl patch deployment ai-orchestrator-api -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"2Gi"}}}]}}}}'
```

---

## Monitoring Best Practices

```bash
# Set up alerts for:
# - Pod crash loops
# - Memory usage > 80%
# - CPU usage > 85%
# - Storage usage > 85%
# - API errors > 5%
# - Response time > 1s (p95)

# Regular health checks
watch -n 5 'kubectl get pods -n ai-orchestrator-prod'
watch -n 5 'kubectl top pods -n ai-orchestrator-prod'
watch -n 5 'kubectl top nodes'
```

---

**Last Updated**: 2024
**Version**: 1.0.0
