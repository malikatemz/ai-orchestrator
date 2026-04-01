# Deployment Guide

## Primary target

The primary deployment path is a single Docker VPS using:

- `docker-compose.prod.yml`
- Caddy for TLS and reverse proxy
- PostgreSQL and Redis as internal-only services
- GitHub Actions for CI and SSH-based deploys

## 1. Provision the server

- Ubuntu 22.04 or newer
- Docker Engine + Docker Compose plugin
- a dedicated app directory such as `/srv/ai-orchestrator`
- DNS records for:
  - `app.yourdomain.com`
  - `api.yourdomain.com`

## 2. Configure environment

Copy `.env.production.example` to `.env.production` and set:

- database credentials
- `PUBLIC_APP_URL`
- `PUBLIC_API_URL`
- `APP_DOMAIN`
- `API_DOMAIN`
- `API_TOKEN` unless you are intentionally running `PUBLIC_DEMO_MODE=true`
- `ALLOWED_ORIGINS`
- optional `SENTRY_DSN`

## 3. Deploy

```bash
chmod +x ops/deploy.sh
./ops/deploy.sh
```

The deploy script:

1. builds the backend, worker, and frontend images
2. starts Postgres and Redis
3. runs `alembic upgrade head`
4. brings up the full stack

## 4. Smoke checks

Verify:

- `https://api.yourdomain.com/health`
- `https://api.yourdomain.com/app-config`
- `https://app.yourdomain.com/`
- `https://app.yourdomain.com/platform-ops`

## 5. Rollback

- restore the previous repo state on the VPS
- rerun `./ops/deploy.sh`
- if needed, restore the database from backup before re-enabling traffic

## 6. GitHub Actions

### CI

`/.github/workflows/ci.yml` validates:

- backend tests
- frontend tests
- frontend production build
- Docker Compose config for dev and prod

### Deploy

`/.github/workflows/deploy.yml` is designed for SSH deploys. Set these secrets:

- `VPS_HOST`
- `VPS_PORT`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_APP_PATH`

The workflow syncs the repo to the server and executes `ops/deploy.sh`.

## 7. Demo vs production

### Demo mode

- `APP_MODE=demo`
- `PUBLIC_DEMO_MODE=true`
- `AUTO_SEED_DEMO=true`

### Production mode

- `APP_MODE=production`
- `PUBLIC_DEMO_MODE=false`
- `AUTO_SEED_DEMO=false`
- `API_TOKEN` must be set

Production must not silently fall back to open access.
