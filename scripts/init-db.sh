#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Stream SQL: works with local or remote Docker daemons; no host bind required.
exists=$(docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT to_regclass('\''public.contracts'\'') IS NOT NULL"')
if [ "$exists" = "f" ]; then
  docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/001_initial.sql
elif [ "$exists" = "t" ]; then
  echo 'Schema already initialized; no changes applied.'
else
  echo 'Unable to determine schema state' >&2
  exit 1
fi
# Additive migrations are designed to run repeatedly without removing data.
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/002_ingestion.sql
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/003_analytics.sql
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/004_workbench.sql

docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/005_accounts.sql
