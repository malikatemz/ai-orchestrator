# Production Debugging Runbook

## 10 Diagnostic Steps

1. Confirm blast radius.
   Check whether the issue affects all requests, one route, one workflow type, or one agent/task path.

2. Capture a failing request reference.
   Use the `x-request-id` header or the frontend error banner reference and search logs/Sentry with that value first.

3. Compare runtime fingerprints.
   Fetch `/diagnostics/runtime` from local and production and compare Python version, platform, DB driver, and safe env values.

4. Check health and degradation mode.
   Call `/health` and verify whether the system is running normally or in queue fallback mode.

5. Inspect structured logs around the failing request.
   Search for `api_error`, `unhandled_exception`, `queue_degraded`, `task_failed`, and matching `request_id` or `task_id`.

6. Reproduce using production-like input, not just production-like code.
   Replay the failing payload, workflow name, task input, and selected agent against staging or a copy of production config.

7. Diff environment and configuration.
   Compare environment variables, dependency versions, container image tags, feature flags, and secrets mount paths.

8. Trace dependency health.
   Verify Postgres latency, Redis connectivity, worker backlog, Sentry issue spikes, and any provider/API errors.

9. Check recent changes.
   Review deploys, schema changes, prompt/output shape changes, env changes, and infrastructure maintenance inside the failure window.

10. Add a permanent detector before closing the incident.
   Convert the discovered signal into a test, log field, Sentry tag, or PagerDuty threshold so the same class of failure is caught next time.

## Environment Diff Checklist

- `APP_ENV`
- `DATABASE_URL` driver and hostname
- `REDIS_URL`
- `LOG_LEVEL`
- `SENTRY_DSN` present or missing
- `SENTRY_TRACES_SAMPLE_RATE`
- frontend `NEXT_PUBLIC_API_BASE_URL`
- frontend `NEXT_PUBLIC_SITE_URL`
- frontend `NEXT_PUBLIC_SENTRY_DSN`
- Python version
- Node version
- OS / container base image
- installed package lockfile versions
- Docker image SHA or deployment artifact version
- feature flags
- worker concurrency settings
- background queue enabled / disabled

## Logging Strategy

Add and keep the following fields on every meaningful event:

- `event`
- `request_id`
- `workflow_id`
- `task_id`
- `code`
- `severity`
- `queue_mode`
- `retry_count`
- `runtime.environment`
- `runtime.database_driver`

Primary log events already implemented:

- `startup_complete`
- `api_error`
- `unhandled_exception`
- `task_queued`
- `queue_dispatch`
- `queue_degraded`
- `task_started`
- `task_completed`
- `task_failed`

## Monitoring Setup

### Sentry

- Backend captures unhandled API and worker exceptions.
- Frontend captures typed API failures and client-side errors.
- Tag all events with `error_code`, `severity`, and `request_id`.

### Metrics to watch

- API 5xx rate
- request latency p95
- task failure rate
- task retry exhaustion count
- queue backlog
- queue degradation duration
- frontend fetch error rate
- crash-free sessions

### PagerDuty thresholds

See `ops/pagerduty-alert-thresholds.yaml`.

## Incident Workflow

1. Pull `request_id`
2. Search logs and Sentry
3. Compare `/diagnostics/runtime`
4. Confirm health / queue mode
5. Reproduce with captured payload
6. Patch and add a regression test before closing
