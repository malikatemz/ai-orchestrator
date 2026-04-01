# 60-Second Demo Script

## Goal

Help a buyer understand the value in under 60 seconds.

The story is not “we built a dashboard.”

The story is:

> when an AI workflow fails, you can see it, retry it, and keep the system moving.

## Demo environment settings

Use:

- `APP_MODE=demo`
- `PUBLIC_DEMO_MODE=true`
- `AUTO_SEED_DEMO=true`

That gives you:

- seeded workflows on startup
- no login friction
- a one-click demo reset button

## Click path

### 1. Open the homepage

Call out:

- seeded workflows
- live metrics
- public demo mode

### 2. Reset demo data

Use the “Reset demo data” button so the state is fresh and deterministic.

### 3. Open a seeded workflow

Pick a workflow that already contains a failed task.

Call out:

- queue lane
- status/stage
- failure visibility

### 4. Retry the failed task

Use the retry button on the failed task card.

Explain:

- the retried task is cloned
- retry lineage is preserved
- the task is requeued instead of silently disappearing

### 5. Dispatch one new task

Create a simple task on the selected workflow.

Explain:

- operators can move from incident visibility to action immediately
- the system records audit events for the dispatch

### 6. Open Platform Ops

Navigate to `/platform-ops` and show:

- failure rate
- queue lanes
- top failing workflows
- audit log events

## Talking points

- “You can see what failed.”
- “You can retry without rebuilding the workflow.”
- “You can inspect queue lanes and audit history.”
- “This is the control layer around AI execution, not just another prompt UI.”

## Demo reset fallback

If the state becomes noisy or confusing:

- click “Reset demo data”
- reload the dashboard
- repeat the workflow -> retry -> ops flow
