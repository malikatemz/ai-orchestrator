# AI Orchestrator Architecture

## Current shipping direction

The current architecture is optimized for a Docker VPS deployment with:

- stateless FastAPI API containers
- Celery workers consuming multiple execution lanes
- Redis as the queue broker
- PostgreSQL for persistence
- Caddy as the public reverse proxy

## Core runtime design

```text
Browser / Operator
  -> Caddy
  -> FastAPI orchestrator
  -> Redis queue
  -> Celery workers
  -> PostgreSQL
```

## Core principles

- Stateless orchestrator: no in-memory workflow truth
- Queue-first execution: tasks flow through lanes instead of direct execution
- Decoupled workers: workers can scale independently from the API
- Auditability: workflow creation, dispatch, retry, and failure events are persisted

## Execution lanes

The first shipping execution lanes are:

- `high_priority`
- `default`
- `low_cost`

They are derived from workflow priority and provide the first step toward SLA-aware routing.

## Scale path

### Phase 1

- single Postgres instance
- single Redis instance
- one API deployment
- one worker deployment

### Phase 2

- read replicas for Postgres
- PgBouncer
- Redis clustering
- autoscaled workers

### Phase 3

- Kafka or another event streaming layer
- service split for orchestrator, execution, and billing
- organization-level sharding
- multi-region failover

## Observability

Primary metrics:

- tasks/sec
- queue depth by lane
- failure rate
- retry rate
- average duration
- top failing workflows

Primary tools:

- structured logs
- Sentry
- ops metrics endpoint
- audit logs
- future Prometheus/Grafana stack

## Enterprise ops foundation

The first enterprise-ops wave centers on:

- audit logs
- admin-only ops endpoints outside demo mode
- queue-lane visibility
- explicit app modes
- production-safe auth requirements

Future enterprise layers:

- RBAC
- SSO
- SLA-aware scheduling
- tenant isolation by org/workspace

## Kubernetes path

Starter manifests live in `ops/k8s/` and cover:

- API Deployment + Service
- Worker Deployment
- Worker HPA

They are intentionally starter scaffolds, not the primary deployment target. KEDA, managed Redis/Postgres, and ingress specifics remain future work.

## Resilience and chaos testing

Planned failure drills:

- kill workers and verify retry/recovery
- flood queues and observe backpressure
- inject DB latency and validate graceful degradation
- simulate API failures and confirm restart/replay behavior

Success criteria:

- no data loss
- retries remain visible
- recovery does not require manual repair for common failure paths

## Optimization engine roadmap

Future differentiation moves beyond execution into optimization:

- model/agent auto-routing
- cached repeated work
- smart retries with alternate agents
- prompt optimization from reliability data
- operator-facing optimization suggestions

## Strategic architecture outcome

The long-term platform controls:

- execution
- observability
- optimization
- monetization
- distribution
