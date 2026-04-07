# Kubernetes Autoscaling Guide - AI Orchestrator

Complete guide for understanding and configuring autoscaling in AI Orchestrator Kubernetes deployment.

## Table of Contents

1. [CPU-Based Scaling](#cpu-based-scaling)
2. [Queue-Depth Scaling (KEDA)](#queue-depth-scaling-keda)
3. [Scaling Behavior](#scaling-behavior)
4. [Cost Optimization](#cost-optimization)
5. [Monitoring & Troubleshooting](#monitoring--troubleshooting)

---

## CPU-Based Scaling

### How It Works

The Horizontal Pod Autoscaler (HPA) monitors CPU utilization and scales replicas based on demand:

1. **Metric Collection**: kubelet collects CPU metrics every 15 seconds
2. **Aggregation**: Metrics Server aggregates metrics across pods
3. **HPA Calculation**: HPA evaluates current vs target utilization
4. **Scaling Decision**: If utilization exceeds target, add/remove pods
5. **Rollout**: New pods are created and traffic is gradually directed to them

### Configuration

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-orchestrator-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-orchestrator-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50  # Scale when > 50% CPU
```

### Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `minReplicas` | 2 | Minimum pods running |
| `maxReplicas` | 10 | Maximum pods allowed |
| `averageUtilization` | 50% | Target CPU utilization |
| `scaleUp.periodSeconds` | 60 | Check every 60 seconds |
| `scaleUp.value` | 100% | Max increase 100% per minute |
| `scaleDown.value` | 50% | Max decrease 50% per minute |
| `scaleDown.stabilization` | 300s | Wait 5 min before scaling down |

### Recommended Targets

| Workload Type | Target CPU |  Min Pods | Max Pods |
|--------------|-----------|----------|---------|
| Development | 70% | 1 | 3 |
| Staging | 60% | 2 | 5 |
| Production (normal) | 50% | 2 | 10 |
| Production (critical) | 40% | 3 | 20 |

### Tuning for Your Workload

```bash
# Check current CPU utilization
kubectl get hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod

# If frequently scaling up, reduce target:
kubectl patch hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod \
  -p '{"spec":{"metrics":[{"resource":{"target":{"averageUtilization":40}}}]}}'

# If rarely scaling, increase target:
kubectl patch hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod \
  -p '{"spec":{"metrics":[{"resource":{"target":{"averageUtilization":60}}}]}}'

# Increase max replicas for burst capacity:
kubectl patch hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod \
  -p '{"spec":{"maxReplicas":20}}'
```

### Load Testing

```bash
# Install load testing tool
# brew install apache2 (for ab)
# or apt-get install apache2-utils

# Perform load test
ab -n 10000 -c 100 http://api.yourdomain.com/api/health

# Monitor scaling during load test
watch -n 1 'kubectl get hpa -n ai-orchestrator-prod'
watch -n 1 'kubectl top pods -n ai-orchestrator-prod'

# Expected behavior:
# 1. CPU usage increases
# 2. HPA detects high utilization
# 3. New pods are created
# 4. Load is distributed across more pods
# 5. CPU usage decreases
```

### Metrics Server Requirements

HPA requires Metrics Server to be installed:

```bash
# Check if Metrics Server is running
kubectl get deployment metrics-server -n kube-system

# Install Metrics Server if needed
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verify it's working
kubectl top nodes
kubectl top pods
```

---

## Queue-Depth Scaling (KEDA)

### How It Works

KEDA (Kubernetes Event-Driven Autoscaling) scales workers based on Celery queue depth:

1. **Queue Polling**: KEDA checks queue depth every 30 seconds
2. **Calculation**: Determines how many pods are needed for the queue
3. **Target Metric**: Usually "tasks per pod"
4. **Scaling**: Adds/removes workers to match queue depth
5. **Scale-to-Zero**: Can scale down to 0 when queue is empty

### Installation

```bash
# Add KEDA Helm repository
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

# Install KEDA operator
helm install keda kedacore/keda \
  --namespace keda \
  --create-namespace

# Verify installation
kubectl get pods -n keda
```

### Configuration

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ai-orchestrator-worker-scaler
spec:
  scaleTargetRef:
    kind: Deployment
    name: ai-orchestrator-worker
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
  - type: redis
    metadata:
      address: "redis-service:6379"
      databaseIndex: "1"
      listName: "celery"
      listLength: "30"  # Target queue size per pod
```

### Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `minReplicaCount` | 1 | Minimum workers |
| `maxReplicaCount` | 20 | Maximum workers |
| `listLength` | 30 | Target tasks per pod |
| `pollingInterval` | 30 | Check every 30 seconds |
| `cooldownPeriod` | 300 | Wait 5 min before scaling down |

### Celery Queue Configuration

```python
# In app/worker.py
CELERY_TASK_ROUTES = {
    'app.worker.tasks.process_request': {'queue': 'default'},
    'app.worker.tasks.ai_intensive': {'queue': 'ai_tasks'},
}

# Queue configuration
CELERYD_CONCURRENCY = 4  # Tasks per worker
CELERYD_PREFETCH_MULTIPLIER = 4
```

### Scaling Examples

**Scenario 1: Queue has 300 tasks**
```
Target queue size: 30 tasks/pod
Pods needed: 300 / 30 = 10 pods
Current pods: 3
Action: Scale UP to 10 pods
```

**Scenario 2: Queue is empty**
```
Queue length: 0
Time since last task: > cooldown (300s)
Action: Scale DOWN to minReplicaCount (1 pod)
```

### Tuning Queue-Depth Scaling

```bash
# Check queue depth
kubectl exec redis-0 -n ai-orchestrator-prod -- redis-cli LLEN celery

# If queue is growing, increase target pods:
kubectl patch ScaledObject ai-orchestrator-worker-scaler \
  -n ai-orchestrator-prod \
  -p '{"spec":{"maxReplicaCount":30}}'

# Adjust target queue size (more aggressive scaling):
kubectl patch ScaledObject ai-orchestrator-worker-scaler \
  -n ai-orchestrator-prod \
  -p '{"spec":{"triggers":[{"metadata":{"listLength":"20"}}]}}'
```

### Monitoring Queue Depth

```bash
# Create a monitoring script
cat > monitor_queue.sh << 'EOF'
#!/bin/bash
while true; do
  QUEUE_SIZE=$(kubectl exec redis-0 -n ai-orchestrator-prod -- \
    redis-cli LLEN celery 2>/dev/null || echo "N/A")
  WORKER_PODS=$(kubectl get pods -l app=ai-orchestrator,component=worker \
    -n ai-orchestrator-prod --no-headers | wc -l)
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
  
  echo "[$TIMESTAMP] Queue: $QUEUE_SIZE tasks | Workers: $WORKER_PODS pods"
  sleep 30
done
EOF

chmod +x monitor_queue.sh
./monitor_queue.sh
```

---

## Scaling Behavior

### Scale-Up Behavior

**Fast Scale-Up** (when load increases rapidly):

```yaml
scaleUp:
  stabilizationWindowSeconds: 0  # No wait before scaling up
  policies:
  - type: Percent
    value: 100  # Double the replicas
    periodSeconds: 60  # Per minute
  - type: Pods
    value: 4  # Or add 4 pods
    periodSeconds: 60
  selectPolicy: Max  # Choose the more aggressive option
```

This means:
- At t=0: 2 pods, sudden 100% CPU usage
- At t=60: Scale to 4 pods (double, or 2 + 4 = max 4)
- At t=120: Scale to 8 pods if still high CPU
- At t=180: Scale to max 10 pods

### Scale-Down Behavior

**Conservative Scale-Down** (to avoid thrashing):

```yaml
scaleDown:
  stabilizationWindowSeconds: 300  # Wait 5 minutes before scaling down
  policies:
  - type: Percent
    value: 50  # Remove 50% of replicas
    periodSeconds: 60
  selectPolicy: Min  # Choose the more conservative option
```

This means:
- At t=0: 10 pods running, low CPU usage
- At t=300: Wait 5 minutes
- At t=360: Check if still low CPU
- At t=360: Scale to 5 pods (50% reduction)
- At t=420: Scale to 2 pods (50% of 5)

### Preventing Flapping

```yaml
# Good configuration (prevents rapid scaling)
behavior:
  scaleUp:
    stabilizationWindowSeconds: 0
    policies:
    - type: Percent
      value: 100
      periodSeconds: 60
  
  scaleDown:
    stabilizationWindowSeconds: 300  # Wait before scaling down
    policies:
    - type: Percent
      value: 50
      periodSeconds: 60

# Bad configuration (causes flapping)
# scaleDown.stabilizationWindowSeconds: 0
# This causes rapid scale up/down if load fluctuates
```

---

## Cost Optimization

### Right-Sizing Resources

```bash
# Check actual resource usage vs requests
kubectl get pods -n ai-orchestrator-prod -o custom-columns=\
  NAME:.metadata.name,\
  CPU_REQ:.spec.containers[0].resources.requests.cpu,\
  CPU_USE:.metrics.containers[0].usage.cpu,\
  MEM_REQ:.spec.containers[0].resources.requests.memory,\
  MEM_USE:.metrics.containers[0].usage.memory

# If requests are too high:
# 1. Monitor actual usage for 1 week
# 2. Reduce requests to ~120% of peak usage
# 3. Increase limits to ~200% for burst capacity

# Example: If actual peak is 300m, set requests: 400m, limits: 600m
```

### Cluster-Level Autoscaling

For cloud providers (AWS, GCP, Azure):

```bash
# AWS EKS - Configure Cluster Autoscaler
kubectl apply -f https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscovery.yaml

# GCP GKE - Already built-in, enable with:
gcloud container clusters update CLUSTER_NAME \
  --enable-autoscaling \
  --min-nodes 3 \
  --max-nodes 10

# Azure AKS - Configure Cluster Autoscaler
az aks update \
  --resource-group myResourceGroup \
  --name myAKSCluster \
  --enable-cluster-autoscaling \
  --min-count 3 \
  --max-count 10
```

### Pod Disruption Budgets

Ensure graceful scaling and updates:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 1  # Always keep at least 1 pod
  selector:
    matchLabels:
      app: ai-orchestrator
      component: api
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: worker-pdb
spec:
  minAvailable: 1  # At least 1 worker running
  selector:
    matchLabels:
      app: ai-orchestrator
      component: worker
```

Apply PDB:
```bash
kubectl apply -f - << 'EOF'
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
  namespace: ai-orchestrator-prod
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: ai-orchestrator
      component: api
EOF
```

---

## Monitoring & Troubleshooting

### Viewing HPA Status

```bash
# Real-time HPA status
kubectl get hpa -n ai-orchestrator-prod -w

# Detailed HPA info
kubectl describe hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod

# HPA events
kubectl get events -n ai-orchestrator-prod | grep HorizontalPodAutoscaler
```

### Common Autoscaling Issues

**Issue**: HPA not scaling despite high CPU

```bash
# Check Metrics Server
kubectl get deployment metrics-server -n kube-system

# Verify metrics are available
kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes
kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/ai-orchestrator-prod/pods

# Check resource requests are defined (HPA needs them)
kubectl get deployment ai-orchestrator-api -n ai-orchestrator-prod -o yaml | grep -A 5 "resources:"
```

**Issue**: Pods keep getting evicted

```bash
# Check node pressure
kubectl describe node <node-name> | grep -A 5 "Conditions:"

# Reduce max replicas or increase node capacity
kubectl patch hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod \
  -p '{"spec":{"maxReplicas":5}}'

# Scale up cluster
# AWS: asg-max-size update
# GCP: gke-scale-cluster
# Azure: az aks scale
```

**Issue**: Scaling is too slow

```bash
# Reduce scale-up stabilization window
kubectl patch hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod \
  -p '{"spec":{"behavior":{"scaleUp":{"stabilizationWindowSeconds":0}}}}'

# Increase scale-up rate
kubectl patch hpa ai-orchestrator-api-hpa -n ai-orchestrator-prod \
  -p '{"spec":{"behavior":{"scaleUp":{"policies":[{"type":"Percent","value":200,"periodSeconds":30}]}}}}'
```

### Load Test & Verify Scaling

```bash
# 1. Baseline check
kubectl get hpa -n ai-orchestrator-prod
kubectl get pods -n ai-orchestrator-prod | grep api | wc -l

# 2. Start monitoring
watch -n 2 'kubectl get hpa -n ai-orchestrator-prod && echo "---" && kubectl get pods -n ai-orchestrator-prod | grep api | wc -l'

# 3. Generate load (in another terminal)
ab -n 100000 -c 200 http://api.yourdomain.com/api/health

# 4. Observe scaling
# - Pods should increase after ~60 seconds
# - CPU should stabilize around target
# - New pods should become ready within 30-60 seconds

# 5. Stop load and observe scale-down
# - Should wait 5 minutes before scaling down
# - Should scale down gradually
```

---

**Last Updated**: 2024
**Version**: 1.0.0
