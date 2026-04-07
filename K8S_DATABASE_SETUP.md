# Kubernetes Database Setup Guide - AI Orchestrator

Guide for setting up and managing PostgreSQL databases in Kubernetes for AI Orchestrator.

## Table of Contents

1. [Self-Managed PostgreSQL](#self-managed-postgresql)
2. [Managed Database Services](#managed-database-services)
3. [Connection Pooling](#connection-pooling)
4. [Migration from VPS](#migration-from-vps)
5. [Monitoring & Tuning](#monitoring--tuning)

---

## Self-Managed PostgreSQL

### StatefulSet Deployment

We provide a production-ready StatefulSet in `day4-postgres-statefulset.yaml`:

```bash
# Deploy PostgreSQL
kubectl apply -f k8s/day4-postgres-statefulset.yaml

# Wait for it to be ready
kubectl wait --for=condition=ready pod postgres-0 \
  -n ai-orchestrator-prod --timeout=300s

# Verify deployment
kubectl get statefulset postgres -n ai-orchestrator-prod
kubectl describe statefulset postgres -n ai-orchestrator-prod
```

### Storage Setup

PostgreSQL requires persistent storage:

```bash
# Check PVC binding
kubectl get pvc -n ai-orchestrator-prod
kubectl describe pvc postgres-data-postgres-0 -n ai-orchestrator-prod

# Check PV provisioning
kubectl get pv

# Monitor storage usage
kubectl exec postgres-0 -n ai-orchestrator-prod -- df -h /var/lib/postgresql/data
```

### High Availability Setup (3 replicas)

For production deployments with automatic failover:

```bash
# Update StatefulSet replicas
kubectl patch statefulset postgres -n ai-orchestrator-prod \
  -p '{"spec":{"replicas":3}}'

# Configure replication in postgres-config ConfigMap
# WAL level: replica
# max_wal_senders: 10
# max_replication_slots: 10

# Set up streaming replication
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT * FROM pg_stat_replication;"

# Create replication slot on primary
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT * FROM pg_create_physical_replication_slot('replica1');"
```

### Connection Management

```bash
# Check active connections
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;"

# View current connections
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT * FROM pg_stat_activity;"

# Kill idle connections
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'ai_orchestrator' AND state = 'idle';"
```

---

## Managed Database Services

### AWS RDS

```bash
# Create RDS instance using AWS CLI
aws rds create-db-instance \
  --db-instance-identifier ai-orchestrator-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.2 \
  --master-username postgres \
  --master-user-password <random-password> \
  --allocated-storage 100 \
  --storage-type gp3 \
  --vpc-security-group-ids sg-xxxxx \
  --db-subnet-group-name ai-orchestrator-subnet \
  --backup-retention-period 30 \
  --multi-az

# Get connection endpoint
aws rds describe-db-instances \
  --db-instance-identifier ai-orchestrator-db \
  --query 'DBInstances[0].Endpoint.Address'

# Create Kubernetes secret
kubectl create secret generic ai-orchestrator-secrets \
  --from-literal=DATABASE_URL="postgresql://postgres:password@ai-orchestrator-db.xxxxx.rds.amazonaws.com:5432/ai_orchestrator" \
  -n ai-orchestrator-prod
```

### GCP Cloud SQL

```bash
# Create Cloud SQL instance
gcloud sql instances create ai-orchestrator-db \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-8192 \
  --region=us-east1 \
  --backup

# Create database
gcloud sql databases create ai_orchestrator \
  --instance=ai-orchestrator-db

# Create user
gcloud sql users create postgres \
  --instance=ai-orchestrator-db \
  --password=<random-password>

# Get connection name
gcloud sql instances describe ai-orchestrator-db --format='value(connectionName)'

# Create Kubernetes secret (using Cloud SQL Proxy)
kubectl create secret generic ai-orchestrator-secrets \
  --from-literal=DATABASE_URL="postgresql://postgres:password@127.0.0.1:5432/ai_orchestrator" \
  -n ai-orchestrator-prod

# Deploy Cloud SQL Proxy sidecar
kubectl patch deployment ai-orchestrator-api \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"cloud-sql-proxy","image":"gcr.io/cloudsql-docker/cloud-sql-proxy:latest","args":["-ip_address_types=PRIVATE","<connection-name>"]}]}}}}'
```

### Azure Database for PostgreSQL

```bash
# Create server
az postgres server create \
  --resource-group myResourceGroup \
  --name ai-orchestrator-db \
  --location eastus \
  --admin-user postgres \
  --admin-password <random-password> \
  --sku-name B_Gen5_2 \
  --storage-size 102400 \
  --backup-retention 30 \
  --geo-redundant-backup Enabled

# Create database
az postgres db create \
  --resource-group myResourceGroup \
  --server-name ai-orchestrator-db \
  --name ai_orchestrator

# Get connection details
az postgres server show \
  --resource-group myResourceGroup \
  --name ai-orchestrator-db

# Create secret
kubectl create secret generic ai-orchestrator-secrets \
  --from-literal=DATABASE_URL="postgresql://postgres@ai-orchestrator-db:password@ai-orchestrator-db.postgres.database.azure.com:5432/ai_orchestrator" \
  -n ai-orchestrator-prod
```

---

## Connection Pooling

### pgBouncer in Kubernetes

```yaml
---
# pgBouncer ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: pgbouncer-config
  namespace: ai-orchestrator-prod
data:
  pgbouncer.ini: |
    [databases]
    ai_orchestrator = host=postgres-service port=5432 dbname=ai_orchestrator
    
    [pgbouncer]
    pool_mode = transaction
    max_client_conn = 1000
    default_pool_size = 25
    min_pool_size = 10
    reserve_pool_size = 5
    reserve_pool_timeout = 3
    max_db_connections = 100
    max_user_connections = 100
    server_idle_timeout = 600
    server_lifetime = 3600
    server_connect_timeout = 15
---
# pgBouncer Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pgbouncer
  namespace: ai-orchestrator-prod
spec:
  replicas: 1
  selector:
    matchLabels:
      app: pgbouncer
  template:
    metadata:
      labels:
        app: pgbouncer
    spec:
      containers:
      - name: pgbouncer
        image: pgbouncer:latest
        ports:
        - containerPort: 6432
        volumeMounts:
        - name: pgbouncer-config
          mountPath: /etc/pgbouncer
      volumes:
      - name: pgbouncer-config
        configMap:
          name: pgbouncer-config
---
# pgBouncer Service
apiVersion: v1
kind: Service
metadata:
  name: pgbouncer
  namespace: ai-orchestrator-prod
spec:
  type: ClusterIP
  ports:
  - port: 5432
    targetPort: 6432
  selector:
    app: pgbouncer
```

Deploy:
```bash
kubectl apply -f pgbouncer.yaml

# Update DATABASE_URL to point to pgbouncer
kubectl set env deployment/ai-orchestrator-api \
  DATABASE_URL="postgresql://postgres:password@pgbouncer:5432/ai_orchestrator" \
  -n ai-orchestrator-prod
```

### PgBouncer Performance

```bash
# Monitor connection pool
kubectl exec pgbouncer-<pod> -n ai-orchestrator-prod -- \
  psql -U postgres -h 127.0.0.1 pgbouncer -c "SHOW POOLS;"

# Check statistics
kubectl exec pgbouncer-<pod> -n ai-orchestrator-prod -- \
  psql -U postgres -h 127.0.0.1 pgbouncer -c "SHOW STATS;"

# Reload configuration without restart
kubectl exec pgbouncer-<pod> -n ai-orchestrator-prod -- \
  psql -U postgres -h 127.0.0.1 pgbouncer -c "RELOAD;"
```

---

## Migration from VPS

### Zero-Downtime Migration

```bash
# 1. Backup VPS database
pg_dump -h vps.example.com -U postgres ai_orchestrator | gzip > vps-backup.sql.gz

# 2. Create Kubernetes database (if not already running)
kubectl apply -f k8s/day4-postgres-statefulset.yaml
kubectl wait --for=condition=ready pod postgres-0 -n ai-orchestrator-prod --timeout=300s

# 3. Restore to Kubernetes
gunzip -c vps-backup.sql.gz | kubectl exec -i postgres-0 \
  -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator

# 4. Set up continuous replication from VPS (optional)
# This creates a logical replication slot on VPS that streams changes to K8s

# 5. Verify data integrity
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "SELECT COUNT(*) FROM users;"

# 6. Failover to Kubernetes
# Update DATABASE_URL in Kubernetes to point to new database

# 7. Monitor for issues (24 hours)
kubectl logs deployment/ai-orchestrator-api -n ai-orchestrator-prod -f

# 8. After stability confirmed, remove VPS database replication
```

### Minimal Downtime Migration

```bash
# 1. Enable maintenance mode on VPS app (0.5 hours downtime)
# Stop API, complete any pending requests

# 2. Final backup from VPS
pg_dump -h vps.example.com -U postgres ai_orchestrator | \
  gzip > final-backup.sql.gz

# 3. Restore to Kubernetes
gunzip -c final-backup.sql.gz | kubectl exec -i postgres-0 \
  -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator

# 4. Update DATABASE_URL in all pods
kubectl set env deployment/ai-orchestrator-api \
  DATABASE_URL="postgresql://postgres:password@postgres-service:5432/ai_orchestrator" \
  -n ai-orchestrator-prod

# 5. Restart pods to pick up new database URL
kubectl rollout restart deployment/ai-orchestrator-api -n ai-orchestrator-prod

# 6. Disable maintenance mode
# Customers can now use Kubernetes-based application
```

---

## Monitoring & Tuning

### Key Metrics to Monitor

```bash
# Connection count
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Query duration (p95)
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY mean_time) FROM pg_stat_statements;"

# Cache hit ratio (should be > 99%)
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT sum(heap_blks_read) / (sum(heap_blks_read) + sum(heap_blks_hit)) FROM pg_statio_user_tables;"

# Replication lag (for HA)
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT * FROM pg_stat_replication;"
```

### Performance Tuning

```bash
# Increase shared_buffers (for large datasets)
# Recommended: 25% of available RAM
kubectl patch statefulset postgres -n ai-orchestrator-prod \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"postgres","env":[{"name":"POSTGRES_INIT_ARGS","value":"-c shared_buffers=2GB"}]}]}}}}'

# Increase work_mem (for complex queries)
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "ALTER SYSTEM SET work_mem = '256MB';"

# Increase effective_cache_size
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "ALTER SYSTEM SET effective_cache_size = '3GB';"

# Reload configuration
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT pg_reload_conf();"
```

---

**Last Updated**: 2024
**Version**: 1.0.0
