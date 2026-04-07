# Kubernetes Cache Setup Guide - AI Orchestrator

Guide for setting up and managing Redis cache in Kubernetes for AI Orchestrator.

## Table of Contents

1. [Self-Managed Redis](#self-managed-redis)
2. [Managed Cache Services](#managed-cache-services)
3. [Monitoring & Tuning](#monitoring--tuning)

---

## Self-Managed Redis

### StatefulSet Deployment

We provide a production-ready StatefulSet in `day4-redis-statefulset.yaml`:

```bash
# Deploy Redis
kubectl apply -f k8s/day4-redis-statefulset.yaml

# Wait for it to be ready
kubectl wait --for=condition=ready pod redis-0 \
  -n ai-orchestrator-prod --timeout=300s

# Verify deployment
kubectl get statefulset redis -n ai-orchestrator-prod
kubectl describe statefulset redis -n ai-orchestrator-prod
```

### Configuration

The Redis deployment includes:
- **Persistence**: RDB snapshots + AOF (Append-Only File)
- **Memory Management**: LRU eviction policy
- **Performance**: Optimized for high throughput
- **Monitoring**: Prometheus metrics export

### Storage Setup

Redis uses persistent storage for durability:

```bash
# Check PVC binding
kubectl get pvc -n ai-orchestrator-prod
kubectl describe pvc redis-data-redis-0 -n ai-orchestrator-prod

# Monitor storage usage
kubectl exec redis-0 -n ai-orchestrator-prod -- df -h /data
```

### Persistence Configuration

Redis uses two persistence mechanisms:

```bash
# Check RDB snapshot status
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli LASTSAVE

# Check AOF status
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli CONFIG GET appendonly

# Manually trigger save
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli SAVE

# Async save (doesn't block)
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli BGSAVE
```

### Redis Cluster Mode (Advanced)

For high availability, scale to 3 replicas:

```bash
# Update StatefulSet replicas
kubectl patch statefulset redis -n ai-orchestrator-prod \
  -p '{"spec":{"replicas":3}}'

# Enable cluster mode in redis-config ConfigMap
kubectl edit configmap redis-config -n ai-orchestrator-prod
# Set: cluster-enabled yes

# Cluster slot allocation (automatic in K8s)
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli CLUSTER INFO

# Check cluster nodes
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli CLUSTER NODES
```

---

## Managed Cache Services

### AWS ElastiCache

```bash
# Create Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id ai-orchestrator-redis \
  --engine redis \
  --cache-node-type cache.t3.micro \
  --engine-version 7.0 \
  --num-cache-nodes 1 \
  --vpc-security-group-ids sg-xxxxx \
  --cache-subnet-group-name ai-orchestrator-subnet \
  --automatic-failover-enabled

# Get endpoint
aws elasticache describe-cache-clusters \
  --cache-cluster-id ai-orchestrator-redis \
  --query 'CacheClusters[0].CacheNodes[0].Endpoint'

# Create Kubernetes secret
kubectl create secret generic ai-orchestrator-secrets \
  --from-literal=REDIS_URL="redis://<endpoint>:6379/0" \
  -n ai-orchestrator-prod
```

### GCP Memorystore

```bash
# Create Redis instance
gcloud redis instances create ai-orchestrator-redis \
  --size=1 \
  --region=us-east1 \
  --redis-version=7.0

# Get host and port
gcloud redis instances describe ai-orchestrator-redis \
  --region=us-east1 \
  --format='value(host,port)'

# Create Kubernetes secret
kubectl create secret generic ai-orchestrator-secrets \
  --from-literal=REDIS_URL="redis://<host>:6379/0" \
  -n ai-orchestrator-prod
```

### Azure Cache for Redis

```bash
# Create cache instance
az redis create \
  --resource-group myResourceGroup \
  --name ai-orchestrator-redis \
  --location eastus \
  --sku Standard \
  --vm-size c0

# Get connection string
az redis show-connection-string \
  --name ai-orchestrator-redis \
  --resource-group myResourceGroup

# Create Kubernetes secret
kubectl create secret generic ai-orchestrator-secrets \
  --from-literal=REDIS_URL="rediss://<password>@<host>:6380/0" \
  -n ai-orchestrator-prod
```

---

## Monitoring & Tuning

### Key Metrics

```bash
# Memory usage
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli INFO memory

# Keyspace metrics
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli INFO keyspace

# Hit rate (should be > 90%)
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli INFO stats | grep -E "hits|misses"

# Connected clients
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli INFO clients

# Slowlog
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli SLOWLOG GET 10
```

### Memory Optimization

```bash
# Check eviction policy
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli CONFIG GET maxmemory-policy

# Set LRU eviction (remove least recently used)
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Monitor memory pressure
watch -n 1 'kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli INFO memory | grep -E "used|max"'

# Analyze key sizes
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli --bigkeys

# Find memory hogs
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli --memkeys
```

### Performance Tuning

```bash
# Increase slowlog threshold (currently 10ms)
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli CONFIG SET slowlog-log-slower-than 5000

# Increase slowlog length
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli CONFIG SET slowlog-max-len 256

# Enable client tracking (for better performance)
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli CLIENT TRACKING ON

# Monitor command latency
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli LATENCY LATEST

# Reset latency stats
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli LATENCY RESET
```

### Cache Strategy

```bash
# Recommended settings for Celery broker:
# Database 0: Session cache (TTL: 1 hour)
# Database 1: Celery tasks broker (persistent)
# Database 2: Result backend (TTL: varies)

# View database sizes
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli INFO keyspace

# Example: Get all keys in DB 1 (Celery)
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli -n 1 KEYS "*" | head -20

# Monitor queue depth
watch -n 5 'kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli -n 1 LLEN celery'
```

---

**Last Updated**: 2024
**Version**: 1.0.0
