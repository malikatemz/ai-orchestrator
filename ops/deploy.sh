#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Starting production deployment from $ROOT_DIR"

docker compose --env-file .env.production -f docker-compose.prod.yml build backend worker frontend
docker compose --env-file .env.production -f docker-compose.prod.yml up -d db redis

echo "Waiting for database and redis to accept connections..."
sleep 8

docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose --env-file .env.production -f docker-compose.prod.yml up -d

echo "Deployment complete."
