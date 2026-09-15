#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${1:-.env.docker.local}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — copy .env.docker.example and set strong placeholder values."
  exit 1
fi

echo "==> Validating compose configuration"
docker compose --env-file "$ENV_FILE" config >/dev/null

echo "==> Building images"
docker compose --env-file "$ENV_FILE" build backend frontend migrate

echo "==> Starting PostgreSQL"
docker compose --env-file "$ENV_FILE" up -d postgres

echo "==> Running database migrations"
docker compose --env-file "$ENV_FILE" --profile tools run --rm migrate

echo "==> Starting application services"
docker compose --env-file "$ENV_FILE" up -d backend frontend

echo "==> Waiting for backend health"
for _ in $(seq 1 30); do
  if curl -fsS "http://localhost:${BACKEND_HOST_PORT:-7273}/api/health/live" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS "http://localhost:${BACKEND_HOST_PORT:-7273}/api/health" | tee /tmp/vms-smoke-health.json
curl -fsS "http://localhost:${FRONTEND_HOST_PORT:-7272}/" | head -c 200 >/dev/null

echo "==> Smoke test passed"
