# Error Handling Strategy

## Objectives

- Give users clear, safe, actionable error messages.
- Produce structured logs that correlate frontend, API, and worker failures.
- Retry only transient failures.
- Degrade gracefully when Redis, workers, or live dashboard refresh are unavailable.
- Alert on sustained business impact instead of isolated noise.

## Error Envelope

All backend failures should return:

```json
{
  "error": {
    "code": "AIORCH-DEP-002",
    "message": "Background queue is degraded; task will run inline.",
    "severity": "medium",
    "retryable": true,
    "details": {}
  },
  "request_id": "d1f8f949-ec4b-4555-8d4f-d389e3296073"
}
```

## Error Code Taxonomy

### Validation

- `AIORCH-VAL-001`: invalid request payload

### Not Found

- `AIORCH-NOTFOUND-001`: workflow not found
- `AIORCH-NOTFOUND-002`: task not found

### Dependency

- `AIORCH-DEP-001`: database unavailable
- `AIORCH-DEP-002`: queue degraded, inline fallback active

### Task Execution

- `AIORCH-TASK-003`: task retry budget exhausted or terminal worker failure

### System

- `AIORCH-SYS-001`: unhandled internal exception

## User-Facing Error Rules

- Validation errors: show inline next to the control.
- API and task failures: show a banner with a request reference when available.
- Live refresh failures: show cached dashboard data and a degraded-state message.
- Never show raw stack traces or provider secrets to end users.

### Current implementation

- Frontend wraps API failures in `ApiClientError` and preserves `request_id`.
- `useDashboard` falls back to the last successful overview during refresh failures.
- The dashboard shows a single banner rather than exploding the full page.

## Logging Strategy

Backend logs are structured JSON via `python-json-logger`.

Required fields:

- `event`
- `code`
- `severity`
- `request_id`
- `workflow_id`
- `task_id`
- `retry_count`
- `queue_mode`

Current implementation:

- API startup and task queue events are logged in `backend/app/main.py`
- worker lifecycle events are logged in `backend/app/worker.py`

## Retry Logic

### Frontend

- Retry only idempotent `GET` requests
- Backoff schedule: `500ms`, `1500ms`, `3500ms`
- Stop retrying immediately for non-retryable API errors

### Worker

- Celery autoretry for transient `ConnectionError` and `TimeoutError`
- Exponential retry backoff with jitter
- Max retries: `5`

Do not retry:

- validation failures
- missing resources
- deterministic serialization issues

## Graceful Degradation

### Redis / Celery unavailable

- API queues inline using `queue_task(...)->inline`
- warning event logged with `AIORCH-DEP-002`

### Live dashboard refresh unavailable

- show last known dashboard data
- show message: `Live data is temporarily unavailable. Showing the last known state.`

### Sentry unavailable

- app keeps working
- logs still flow to stdout

## Sentry Integration

### Backend

- optional via `SENTRY_DSN`
- initialized through `backend/app/observability.py`
- captures API exceptions and worker failures

### Frontend

- `@sentry/nextjs` initialized in `frontend/sentry.client.config.js`
- typed API and client errors are reported through `frontend/src/lib/monitoring.ts`

## PagerDuty Severity Thresholds

### `SEV-1 Critical`

- API 5xx rate > `15%` for `5m`
- database unavailable for `2m`
- task failure rate > `40%` for `10m`
- zero successful task completions for `15m` during active traffic
- Action: immediate PagerDuty page

### `SEV-2 High`

- API 5xx rate > `5%` for `10m`
- worker backlog > `500` tasks for `15m`
- inline fallback active continuously for `15m`
- task retry exhaustion > `25` tasks in `15m`
- Action: urgent PagerDuty alert

### `SEV-3 Medium`

- Redis unavailable with healthy inline fallback for `5m`
- frontend fetch error rate > `3%` for `15m`
- task latency p95 > `30s` for `15m`
- repeated identical dependency failures `20+` times in `30m`
- Action: Slack or incident channel alert, no default page

### `SEV-4 Low`

- isolated validation spikes
- single task failures below normal baseline
- not-found spikes without revenue impact
- Action: no page, ticket or weekly review only

## Files Implementing This

- `backend/app/error_handling.py`
- `backend/app/observability.py`
- `backend/app/main.py`
- `backend/app/worker.py`
- `frontend/src/services/orchestratorApi.ts`
- `frontend/src/hooks/useDashboard.ts`
- `frontend/src/lib/monitoring.ts`
- `frontend/sentry.client.config.js`
- `frontend/sentry.server.config.js`
- `ops/pagerduty-alert-thresholds.yaml`
