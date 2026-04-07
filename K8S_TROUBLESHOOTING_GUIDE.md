# Kubernetes Troubleshooting Guide - AI Orchestrator

Complete troubleshooting guide for common issues in Kubernetes deployments.

## Table of Contents

1. [Debugging Checklist](#debugging-checklist)
2. [Pod Issues](#pod-issues)
3. [Network Issues](#network-issues)
4. [Storage Issues](#storage-issues)
5. [Database Issues](#database-issues)
6. [Application Issues](#application-issues)
7. [Debugging Tools](#debugging-tools)

---

## Debugging Checklist

Start with this systematic approach:

```bash
# 1. Check pod status
kubectl get pods -n ai-orchestrator-prod
kubectl describe pod <pod-name> -n ai-orchestrator-prod

# 2. Check pod logs
kubectl logs <pod-name> -n ai-orchestrator-prod
kubectl logs <pod-name> -n ai-orchestrator-prod --previous  # If crashed

# 3. Check events
kubectl get events -n ai-orchestrator-prod | grep <pod-name>

# 4. Check resource usage
kubectl top pod <pod-name> -n ai-orchestrator-prod
kubectl top nodes

# 5. Check service connectivity
kubectl get svc -n ai-orchestrator-prod
kubectl describe svc <service-name> -n ai-orchestrator-prod

# 6. Check resource availability
kubectl get pvc -n ai-orchestrator-prod
kubectl get pv
kubectl describe pvc <pvc-name> -n ai-orchestrator-prod

# 7. Check network policies
kubectl get networkpolicy -n ai-orchestrator-prod
```

---

## Pod Issues

### Pod Won't Start (Pending)

**Symptoms**: Pod stuck in Pending state for > 5 minutes

```bash
# Get detailed information
kubectl describe pod <pod-name> -n ai-orchestrator-prod

# Look for messages like:
# - Insufficient memory/cpu: increase node capacity
# - Unbound PVC: fix storage provisioner
# - Node selector mismatch: check node labels
```

**Solutions**:

```bash
# 1. Check available resources on nodes
kubectl describe nodes
kubectl top nodes

# 2. If insufficient resources:
# - Increase cluster size (add more nodes)
# - Reduce pod resource requests
# - Delete low-priority pods

# 3. If PVC issue:
kubectl get pvc -n ai-orchestrator-prod
kubectl describe pvc <pvc-name> -n ai-orchestrator-prod

# 4. If node selector issue:
kubectl get nodes --show-labels
kubectl patch pod <pod-name> -n ai-orchestrator-prod \
  -p '{"spec":{"nodeSelector":null}}'
```

### Pod in CrashLoopBackOff

**Symptoms**: Pod keeps restarting, seen in Events as "Back-off restarting failed container"

```bash
# Check logs from crashed container
kubectl logs <pod-name> -n ai-orchestrator-prod

# Check logs from previous instance
kubectl logs <pod-name> -n ai-orchestrator-prod --previous

# Check restart count
kubectl get pod <pod-name> -n ai-orchestrator-prod -o jsonpath='{.status.containerStatuses[0].restartCount}'
```

**Common causes and solutions**:

```bash
# 1. Application crashing on startup
# Check logs for errors
kubectl logs <pod-name> -n ai-orchestrator-prod | tail -50

# 2. Missing environment variables
kubectl describe pod <pod-name> -n ai-orchestrator-prod | grep -A 20 "Environment:"

# 3. Health check failing
# Temporarily disable liveness probe for debugging:
kubectl patch deployment ai-orchestrator-api -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","livenessProbe":null}]}}}}'

# 4. Resource limits exceeded
kubectl top pod <pod-name> -n ai-orchestrator-prod
# Increase limits if usage is near limit

# 5. Database/Redis not accessible
kubectl exec <pod-name> -n ai-orchestrator-prod -- \
  nc -zv postgres-service 5432
kubectl exec <pod-name> -n ai-orchestrator-prod -- \
  nc -zv redis-service 6379
```

### Pod in ImagePullBackOff

**Symptoms**: Pod fails to pull container image from registry

```bash
# Check image configuration
kubectl describe pod <pod-name> -n ai-orchestrator-prod | grep Image

# Common issues:
# 1. Image not found in registry
#    - Check image name and tag
#    - Verify image is pushed to registry

# 2. Registry credentials missing
#    - Check imagePullSecrets in pod spec
#    - Verify credentials are correct

# 3. Image pull rate limit
#    - Wait and retry
#    - Use image pull secret for authentication
```

**Solutions**:

```bash
# 1. For local testing, use image from local Docker daemon
kubectl set image deployment/ai-orchestrator-api \
  api=ai-orchestrator:latest \
  --local -o yaml | kubectl apply -f -

# 2. Create image pull secret
kubectl create secret docker-registry regcred \
  --docker-server=<registry> \
  --docker-username=<username> \
  --docker-password=<password> \
  -n ai-orchestrator-prod

# 3. Add to pod spec
kubectl patch deployment ai-orchestrator-api -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"regcred"}]}}}}'
```

### Pod in NotReady/Init

**Symptoms**: Pod exists but is not ready to receive traffic

```bash
# Check init containers
kubectl get pod <pod-name> -n ai-orchestrator-prod -o jsonpath='{.status.initContainerStatuses}'

# Check init container logs
kubectl logs <pod-name> -n ai-orchestrator-prod -c wait-for-dependencies

# Common issues:
# - Database not ready
# - Redis not available
# - Health check failing
```

**Solutions**:

```bash
# 1. Verify dependencies are running
kubectl get pod postgres-0 -n ai-orchestrator-prod
kubectl get pod redis-0 -n ai-orchestrator-prod

# 2. Manually run init container commands
kubectl exec <pod-name> -n ai-orchestrator-prod -- \
  nc -zv postgres-service 5432

# 3. Increase init container timeout
kubectl patch deployment ai-orchestrator-api -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"initContainers":[{"name":"wait-for-dependencies","timeoutSeconds":60}]}}}}'
```

---

## Network Issues

### Service Not Accessible

**Symptoms**: Cannot reach service even though pods are running

```bash
# 1. Check service endpoints
kubectl get endpoints -n ai-orchestrator-prod

# Should show pod IPs, if empty the service selector is wrong

# 2. Check service configuration
kubectl describe svc <service-name> -n ai-orchestrator-prod

# 3. Test DNS resolution
kubectl run -it --rm debug --image=alpine --restart=Never \
  -n ai-orchestrator-prod -- \
  sh -c "nslookup ai-orchestrator-api"

# 4. Test connectivity
kubectl run -it --rm debug --image=alpine --restart=Never \
  -n ai-orchestrator-prod -- \
  sh -c "nc -zv ai-orchestrator-api 8000"
```

**Solutions**:

```bash
# 1. Fix service selector
kubectl get pods -n ai-orchestrator-prod --show-labels
# Compare pod labels with service selector

# 2. Re-create service if selector is wrong
kubectl delete svc ai-orchestrator-api -n ai-orchestrator-prod
kubectl apply -f k8s/day2-service.yaml

# 3. Check service ports
kubectl get svc ai-orchestrator-api -n ai-orchestrator-prod -o yaml | grep -A 10 "ports:"
```

### DNS Not Working

**Symptoms**: Pod can't resolve DNS names like `postgres-service`

```bash
# 1. Check DNS service
kubectl get pods -n kube-system | grep coredns

# 2. Test DNS from pod
kubectl exec <pod-name> -n ai-orchestrator-prod -- \
  nslookup kubernetes.default

# 3. Check DNS logs
kubectl logs -n kube-system -l k8s-app=kube-dns | tail -50

# 4. Check resolv.conf in pod
kubectl exec <pod-name> -n ai-orchestrator-prod -- cat /etc/resolv.conf
```

**Solutions**:

```bash
# 1. Restart CoreDNS
kubectl rollout restart deployment coredns -n kube-system

# 2. Scale down and up coredns
kubectl scale deployment coredns --replicas=0 -n kube-system
kubectl scale deployment coredns --replicas=2 -n kube-system

# 3. Check node DNS
kubectl describe node <node-name> | grep -i dns
```

### Network Policy Blocking Traffic

**Symptoms**: Service works from one pod but not another

```bash
# Check network policies
kubectl get networkpolicy -n ai-orchestrator-prod

# View specific policy
kubectl describe networkpolicy allow-api-to-postgres -n ai-orchestrator-prod

# Test connectivity between pods
kubectl exec <pod-name> -n ai-orchestrator-prod -- \
  nc -zv postgres-service 5432
```

**Solutions**:

```bash
# 1. Temporarily remove network policies for debugging
kubectl delete networkpolicy --all -n ai-orchestrator-prod

# 2. Test if connectivity works
kubectl exec <pod-name> -n ai-orchestrator-prod -- \
  nc -zv postgres-service 5432

# 3. If it works, reapply policies and debug selectors
kubectl apply -f k8s/day3-network-policy.yaml

# 4. Fix network policy selectors if needed
kubectl edit networkpolicy allow-api-to-postgres -n ai-orchestrator-prod
```

---

## Storage Issues

### PVC Stuck in Pending

**Symptoms**: PersistentVolumeClaim not bound to PersistentVolume

```bash
# Check PVC status
kubectl get pvc -n ai-orchestrator-prod
kubectl describe pvc postgres-pvc -n ai-orchestrator-prod

# Check available PVs
kubectl get pv

# Check storage class
kubectl get storageclass
kubectl describe storageclass standard
```

**Solutions**:

```bash
# 1. Create matching PV if using manual provisioning
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: PersistentVolume
metadata:
  name: postgres-pv
spec:
  capacity:
    storage: 100Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: standard
  hostPath:
    path: /data/postgres
EOF

# 2. If using cloud storage, create storage class
kubectl apply -f - << 'EOF'
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
EOF

# 3. Re-create PVC with correct storage class
kubectl delete pvc postgres-pvc -n ai-orchestrator-prod
# Edit day2-pvc.yaml to use correct storageClassName
kubectl apply -f k8s/day2-pvc.yaml
```

### Out of Disk Space

**Symptoms**: Pod gets evicted due to disk pressure

```bash
# Check node disk usage
kubectl describe node <node-name> | grep -A 5 "Conditions:"

# Check pod storage usage
kubectl exec <pod-name> -n ai-orchestrator-prod -- df -h /

# Check PVC usage
kubectl exec postgres-0 -n ai-orchestrator-prod -- df -h /var/lib/postgresql/data
```

**Solutions**:

```bash
# 1. Clean up old logs/data
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "VACUUM ANALYZE;"

# 2. Expand PVC (if storage class supports it)
kubectl patch pvc postgres-pvc -n ai-orchestrator-prod \
  -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'

# 3. Increase node disk capacity
# For cloud: scale storage volume
# For on-prem: add disk to node

# 4. Clean up temporary files
kubectl exec <pod-name> -n ai-orchestrator-prod -- rm -rf /tmp/*
```

---

## Database Issues

### Database Connection Refused

**Symptoms**: Application can't connect to PostgreSQL

```bash
# Test connectivity
kubectl exec <pod-name> -n ai-orchestrator-prod -- \
  nc -zv postgres-service 5432

# Check database pod is running
kubectl get pod postgres-0 -n ai-orchestrator-prod
kubectl describe pod postgres-0 -n ai-orchestrator-prod

# Check database logs
kubectl logs postgres-0 -n ai-orchestrator-prod | tail -50

# Test with psql
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -d ai_orchestrator -c "SELECT 1;"
```

**Solutions**:

```bash
# 1. Restart database
kubectl delete pod postgres-0 -n ai-orchestrator-prod
kubectl wait --for=condition=ready pod postgres-0 -n ai-orchestrator-prod --timeout=300s

# 2. Check credentials
kubectl get secret ai-orchestrator-secrets -n ai-orchestrator-prod \
  -o jsonpath='{.data.DATABASE_URL}' | base64 -d

# 3. Fix connection string format
# Format: postgresql://username:password@host:port/database

# 4. Check database initialization
kubectl logs postgres-0 -n ai-orchestrator-prod | grep -i "error\|fail"
```

### Database Slow Queries

**Symptoms**: Application is slow, database queries taking long time

```bash
# Enable slow query log
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "ALTER SYSTEM SET log_min_duration_statement = 1000;"

# Reload configuration
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT pg_reload_conf();"

# View slow queries
kubectl logs postgres-0 -n ai-orchestrator-prod | grep -i "duration:"

# Analyze query plans
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "EXPLAIN SELECT * FROM users WHERE email = 'test@test.com';"
```

**Solutions**:

```bash
# 1. Create missing indexes
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "CREATE INDEX idx_users_email ON users(email);"

# 2. Analyze and vacuum
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "ANALYZE; VACUUM;"

# 3. Increase shared_buffers
kubectl patch statefulset postgres -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"postgres","env":[{"name":"POSTGRES_INITDB_ARGS","value":"-c shared_buffers=512MB"}]}]}}}}'

# 4. Scale up database resources
kubectl patch statefulset postgres -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"postgres","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
```

---

## Application Issues

### High Memory Usage

**Symptoms**: Pods getting OOMKilled or pod using > 80% of limit

```bash
# Check memory usage
kubectl top pod -n ai-orchestrator-prod
kubectl describe pod <pod-name> -n ai-orchestrator-prod | grep -A 5 "Last State:"

# Check if OOMKilled
kubectl get pod <pod-name> -n ai-orchestrator-prod -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
```

**Solutions**:

```bash
# 1. Increase memory limit
kubectl patch deployment ai-orchestrator-api -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"2Gi"}}}]}}}}'

# 2. Check for memory leaks in application
# - Look for unbounded caches
# - Check database connection pool
# - Reduce cache TTL

# 3. Scale horizontally (more pods, less memory each)
kubectl scale deployment ai-orchestrator-api --replicas=5 -n ai-orchestrator-prod
kubectl patch deployment ai-orchestrator-api -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"512Mi"}}}]}}}}'
```

### High CPU Usage

**Symptoms**: Pod CPU maxing out, application slow

```bash
# Monitor CPU usage
kubectl top pod -n ai-orchestrator-prod --containers
watch 'kubectl top pods -n ai-orchestrator-prod'

# Check HPA status
kubectl get hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod
```

**Solutions**:

```bash
# 1. Let HPA scale up pods
kubectl get hpa -n ai-orchestrator-prod --watch

# 2. If HPA not working, scale manually
kubectl scale deployment ai-orchestrator-api --replicas=10 -n ai-orchestrator-prod

# 3. Profile application for hot code paths
# Use Python cProfile or similar

# 4. Optimize slow operations
# - Batch database queries
# - Add caching
# - Use async operations
```

---

## Debugging Tools

### Port Forwarding

```bash
# Forward to API service
kubectl port-forward svc/ai-orchestrator-api 8000:8000 -n ai-orchestrator-prod &

# Forward to specific pod
kubectl port-forward pod/postgres-0 5432:5432 -n ai-orchestrator-prod &

# Forward to Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n ai-orchestrator-prod &

# Access on localhost
curl http://localhost:8000/health
psql -h localhost -U postgres -d ai_orchestrator
# Open http://localhost:9090 in browser
```

### Debug Pod

```bash
# Create a debug pod for testing
kubectl run -it --rm debug \
  --image=alpine \
  --restart=Never \
  -n ai-orchestrator-prod \
  -- sh

# Inside debug pod:
apk add curl netcat-openbsd postgresql-client redis

# Test connectivity
curl http://ai-orchestrator-api:8000/health
nc -zv postgres-service 5432
nc -zv redis-service 6379
redis-cli -h redis-service ping
psql -h postgres-service -U postgres -d ai_orchestrator -c "SELECT 1;"
```

### View Metrics

```bash
# Check kubelet metrics
kubectl get --raw /metrics
kubectl get --raw /metrics | grep container_memory_working_set_bytes | head -5

# Check node metrics
kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes

# Check pod metrics
kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/ai-orchestrator-prod/pods
```

### Get Raw Logs from Node

```bash
# SSH to node
kubectl debug node/<node-name> -it --image=ubuntu

# Check system logs
journalctl -u kubelet -n 100
journalctl -u docker -n 100

# Check disk usage
df -h
du -sh /var/lib/docker

# Check container logs directly
ls -la /var/log/containers/
```

---

**Last Updated**: 2024
**Version**: 1.0.0
