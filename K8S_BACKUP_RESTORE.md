# Kubernetes Backup & Restore Guide - AI Orchestrator

Complete guide for backing up and restoring AI Orchestrator data in Kubernetes environments.

## Table of Contents

1. [Backup Strategy](#backup-strategy)
2. [Database Backups](#database-backups)
3. [Application Data Backups](#application-data-backups)
4. [Restore Procedures](#restore-procedures)
5. [Testing Backups](#testing-backups)

---

## Backup Strategy

### RPO & RTO Targets

| Metric | Target | Method |
|--------|--------|--------|
| RPO (Recovery Point Objective) | 1 hour | Hourly incremental + daily full |
| RTO (Recovery Time Objective) | 4 hours | Restore from backups + rebuild cache |
| Retention | 30 days | Automated cleanup |
| Geographic Redundancy | Multi-region | S3/GCS cross-region replication |

### Backup Schedule

```
Daily at 2 AM UTC:
  - Full database backup (pg_dump)
  - RDB snapshot from Redis
  - Application config backup

Hourly (1 AM, 2 AM, ... 11 PM UTC):
  - Incremental WAL backup from PostgreSQL
  - Redis AOF archiving

Weekly (Sundays at 3 AM UTC):
  - Full system backup including PVCs
  - Backup verification
  - Backup restore drill
```

### Storage Locations

```
Primary:    S3 (ai-orchestrator-backups bucket)
Secondary:  GCS (cross-region replication)
Onsite:     Local NFS (for quick restore)

S3 Bucket Structure:
  /database/full/
    db-backup-2024-01-15-020000.sql.gz
  /database/wal/
    wal-backup-2024-01-15-0100.tar.gz
  /redis/
    redis-dump-2024-01-15.rdb
  /config/
    config-backup-2024-01-15.tar.gz
```

---

## Database Backups

### Automated Backup (CronJob)

```bash
# The automated backup runs daily (already deployed in day4-postgres-backup.yaml)
kubectl get cronjob postgres-backup -n ai-orchestrator-prod

# View backup schedule
kubectl describe cronjob postgres-backup -n ai-orchestrator-prod

# Manually trigger backup
kubectl create job --from=cronjob/postgres-backup manual-backup \
  -n ai-orchestrator-prod

# Monitor backup job
kubectl logs job/manual-backup -n ai-orchestrator-prod -f

# Check if backup was uploaded to S3
aws s3 ls s3://ai-orchestrator-backups/database/full/
```

### Manual Database Backup

```bash
# Full backup with compression
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  pg_dump -U postgres --format=custom --compress=9 ai_orchestrator \
  > backup-$(date +%Y%m%d-%H%M%S).dump

# Backup specific table
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  pg_dump -U postgres -t users ai_orchestrator > users-backup.sql

# Backup with data only (no schema)
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  pg_dump -U postgres --data-only ai_orchestrator > data-only.sql

# Backup with schema only
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  pg_dump -U postgres --schema-only ai_orchestrator > schema-only.sql
```

### WAL Archiving (Continuous Backup)

```bash
# Enable WAL archiving for point-in-time recovery
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "ALTER SYSTEM SET archive_mode = on;"

# Set archiving command (example: to local path)
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "ALTER SYSTEM SET archive_command = 'test ! -f /backup/wal/%f && cp %p /backup/wal/%f';"

# Reload configuration
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SELECT pg_reload_conf();"

# Verify archiving
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "SHOW archive_command;"
```

### Redis Backup

```bash
# Trigger RDB snapshot
kubectl exec redis-0 -n ai-orchestrator-prod -- redis-cli SAVE

# Copy backup to local machine
kubectl cp redis-0:/data/dump.rdb ./redis-dump-$(date +%Y%m%d).rdb \
  -n ai-orchestrator-prod

# Verify backup file
ls -lh redis-dump-*.rdb
```

---

## Application Data Backups

### PVC Snapshots (Cloud Storage)

```bash
# AWS EBS Snapshots
aws ec2 create-snapshot \
  --volume-id <volume-id> \
  --description "AI Orchestrator backup $(date)"

# GCP Persistent Disk Snapshots
gcloud compute disks snapshot <disk-name> \
  --snapshot-names=backup-$(date +%Y%m%d)

# Azure Snapshots
az snapshot create \
  --resource-group myResourceGroup \
  --name backup-$(date +%Y%m%d) \
  --source <disk-id>
```

### Configuration Backups

```bash
# Backup all ConfigMaps
kubectl get configmap -n ai-orchestrator-prod -o yaml \
  > configmap-backup-$(date +%Y%m%d).yaml

# Backup all Secrets (encrypted)
kubectl get secret -n ai-orchestrator-prod -o yaml \
  | gzip -9 \
  > secrets-backup-$(date +%Y%m%d).yaml.gz

# Backup complete namespace state
kubectl get all,cm,secret,pvc,pv,ing,netpol \
  -n ai-orchestrator-prod -o yaml \
  > namespace-backup-$(date +%Y%m%d).yaml

# Upload to S3
aws s3 cp namespace-backup-*.yaml s3://ai-orchestrator-backups/config/
```

---

## Restore Procedures

### Full Database Restore

```bash
# 1. Stop application to prevent writes
kubectl scale deployment ai-orchestrator-api --replicas=0 -n ai-orchestrator-prod
kubectl scale deployment ai-orchestrator-worker --replicas=0 -n ai-orchestrator-prod

# 2. Delete and recreate PostgreSQL pod
kubectl delete pod postgres-0 -n ai-orchestrator-prod
kubectl wait --for=condition=ready pod postgres-0 \
  -n ai-orchestrator-prod --timeout=300s

# 3. Create empty database
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "CREATE DATABASE ai_orchestrator;"

# 4. Restore from backup file
gunzip -c backup.sql.gz | kubectl exec -i postgres-0 \
  -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator

# 5. Verify restore
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "SELECT COUNT(*) FROM users;"

# 6. Restart application
kubectl scale deployment ai-orchestrator-api --replicas=2 -n ai-orchestrator-prod
kubectl scale deployment ai-orchestrator-worker --replicas=2 -n ai-orchestrator-prod

# 7. Verify application is working
kubectl wait --for=condition=ready pod \
  -l app=ai-orchestrator,component=api \
  -n ai-orchestrator-prod --timeout=300s
```

### Point-in-Time Recovery (PITR)

```bash
# 1. Restore from full backup
gunzip -c backup-2024-01-15.sql.gz | kubectl exec -i postgres-0 \
  -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator

# 2. Set recovery target (all WAL files must be available)
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "ALTER SYSTEM SET recovery_target_timeline = 'latest';"

# 3. Create recovery.signal file (PostgreSQL will stop at recovery_target_time)
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  touch /var/lib/postgresql/data/pgdata/recovery.signal

# 4. Specify recovery time
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres -c "ALTER SYSTEM SET recovery_target_time = '2024-01-15 14:30:00';"

# 5. Restart PostgreSQL
kubectl delete pod postgres-0 -n ai-orchestrator-prod

# 6. Verify recovery
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "SELECT * FROM audit_log WHERE event_time > '2024-01-15 14:25:00';"
```

### Partial Restore (Single Table)

```bash
# 1. Get table schema
pg_restore -t users --schema-only backup.dump > users-schema.sql

# 2. Create table in current database
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator < users-schema.sql

# 3. Restore table data
pg_restore -t users --data-only backup.dump | kubectl exec -i postgres-0 \
  -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator

# 4. Verify restore
kubectl exec postgres-0 -n ai-orchestrator-prod -- \
  psql -U postgres ai_orchestrator -c "SELECT COUNT(*) FROM users;"
```

### Redis Data Restore

```bash
# 1. Copy backup file to Redis pod
kubectl cp ./redis-dump.rdb redis-0:/data/ \
  -n ai-orchestrator-prod

# 2. Stop Redis
kubectl delete pod redis-0 -n ai-orchestrator-prod

# 3. Restart Redis (it will load the dump file)
kubectl wait --for=condition=ready pod redis-0 \
  -n ai-orchestrator-prod --timeout=300s

# 4. Verify data
kubectl exec redis-0 -n ai-orchestrator-prod -- \
  redis-cli INFO keyspace
```

---

## Testing Backups

### Backup Verification

```bash
# 1. Automated verification (in backup CronJob)
# Tests backup file integrity
pg_restore --list backup.dump > /dev/null

# 2. Manual verification
pg_restore --list backup.dump | head -20

# 3. Verify backup size and compression ratio
ls -lh backup*.gz
file backup*.gz  # Should show gzip file
```

### Restore Drill (Monthly)

```bash
# 1. Create test namespace
kubectl create namespace ai-orchestrator-test

# 2. Deploy PostgreSQL in test namespace
kubectl apply -f k8s/day4-postgres-statefulset.yaml \
  -n ai-orchestrator-test

# 3. Restore from backup
kubectl cp ./backup.sql.gz postgres-0:/backup.sql.gz \
  -n ai-orchestrator-test

gunzip -c backup.sql.gz | kubectl exec -i postgres-0 \
  -n ai-orchestrator-test -- \
  psql -U postgres ai_orchestrator

# 4. Verify data integrity
kubectl exec postgres-0 -n ai-orchestrator-test -- \
  psql -U postgres ai_orchestrator -c "
    SELECT 
      tablename,
      (CAST(pg_total_relation_size(tablename) AS FLOAT) / 1024 / 1024)::INT AS size_mb
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY size_mb DESC;
  "

# 5. Run consistency checks
kubectl exec postgres-0 -n ai-orchestrator-test -- \
  psql -U postgres ai_orchestrator -c "
    SELECT schemaname, COUNT(*) as tables 
    FROM pg_tables 
    WHERE schemaname NOT IN ('pg_catalog', 'information_schema') 
    GROUP BY schemaname;
  "

# 6. Record results
echo "Restore drill completed successfully on $(date)" >> backup-test-log.txt

# 7. Clean up test resources
kubectl delete namespace ai-orchestrator-test
```

---

## Disaster Recovery Plan

### Critical System Failure

```bash
# 1. Identify what was lost
# - Check latest backup timestamp
# - Determine data loss window
# - Notify stakeholders about RPO/RTO

# 2. Provision new cluster (if needed)
# - Use Infrastructure-as-Code to recreate cluster
# - Provision with same resource specifications

# 3. Restore backups in order
# 1. Database schema and data
# 2. Redis cache (not critical, can be regenerated)
# 3. Application configurations
# 4. DNS/Ingress updates

# 4. Verification
# - Health checks pass
# - Data integrity confirmed
# - All services responding

# 5. Communication
# - Notify users of restoration
# - Monitor for issues
# - Prepare postmortem
```

---

**Last Updated**: 2024
**Version**: 1.0.0
