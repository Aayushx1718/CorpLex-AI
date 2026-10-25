# Run and package CorpLex AI

## Easiest local option — Docker only

Install Git and Docker Desktop (running Linux containers). Node/Python/uv are not required on the host for the container workflow. From a cloned repository in VS Code's terminal, PowerShell, Git Bash or another shell:

```bash
docker compose -p corplex-app -f compose.app.yaml up --build -d --wait
```

The web service listens on your own computer's loopback port **8080**. Use that local port in your browser. The API is proxied through the web service; PostgreSQL is internal. The app stack has a separate volume/project from the earlier host-development database. First startup applies data-preserving migrations automatically. Use `docker compose -p corplex-app -f compose.app.yaml logs --tail 80` for startup problems.

Stop with `docker compose -p corplex-app -f compose.app.yaml stop`. Do not delete named volumes containing documents you want to retain. Container processes do not survive an environment publication/restart automatically; run the startup command again. Use `APP_PORT` to choose another loopback port if 8080 is occupied.

The default mode is trusted local development with no login/token. Use original synthetic samples; no confidential files are needed. Set tokens before any shared/public operation. Public website deployment is a separate action requiring a host/domain and deployment credentials.

## Host development and Windows

The existing FastAPI/Vite workflow remains available in README.md. After starting the database, migrations can now run cross-platform from `backend/`:

```bash
uv run --frozen --group ml python -m app.migrate
uv run --frozen --group ml uvicorn app.main:app --port 8000
```

The migration runner serializes schema updates with an advisory lock, bootstraps an absent schema and applies additive migrations without deleting data. Start `npm run dev` in `frontend/` in another terminal. No Git Bash-only migration command is required on Windows.

## ML in containers

The default image includes research/analytics dependencies but excludes the optional ML group and trained pickle artifacts. A clean image therefore does not claim a trained clause model. Build with `INCLUDE_ML=true` (Compose build argument) and mount **only trusted locally generated** `artifacts/ml/` read-only at `/app/artifacts/ml` if the classifier is required. Use the same locked dependency versions as training and retain report/model hashes. Data caches and user documents are not baked into images; never download/load arbitrary pickle models.

## Corporate/cloud build proxies

Normal Docker builds use the registry trust store and lockfile hashes. The current cloud machine routes network access through an injected proxy, while Docker build containers cannot resolve its host-only service name. `python scripts/build_containers.py` supports that environment by resolving the provided proxy address and supplying its public CA through an ephemeral BuildKit secret. It never disables TLS, npm integrity or artifact checksums, and never prints credentials. Authenticated proxy URLs are intentionally refused. Default local Docker/CI builds need no special proxy setup.

## Protected deployment configuration

Set distinct strong `CORPLEX_ACCESS_TOKEN` / `CORPLEX_REVIEW_TOKEN`, a nondefault `POSTGRES_PASSWORD`, and an explicit percent-encoded `CONTAINER_DATABASE_URL` pointing to `db`. Changing an environment variable does not change the password in an already initialized database; rotate it using reviewed database administration, not by deleting data. Set `APP_ENV=production`, explicit `CORS_ORIGINS` and `ALLOWED_HOSTS`. Keep real values outside Git in securely managed runtime settings. The example file contains development defaults only.

The sample stack binds only loopback. A real host must provide HTTPS termination and private backend/database networking. Do not expose the development stack directly to the Internet. Base image tags should be refreshed, scanned and pinned to reviewed digests for an actual release. See workflows-security.md for the remaining release gates.

## Backup and recovery

Use `pg_dump` against the PostgreSQL service and store the backup outside checkout roots/volumes, with appropriate encryption and access controls. Restore into a separate database and verify original byte hashes, counts and source offsets before relying on it. Never dump credentials or confidential contract content into CI logs. Docker volumes may not be retained by cloud environment snapshots; back up documents explicitly. A scheduled backup/retention service is not implemented by this repository.

## CI

`.github/workflows/ci.yml` runs locked installation, the complete PostgreSQL-backed test suite, frontend tests/build, and a Docker stack startup/liveness check. CI has read-only repository permissions and no LLM credentials. It cleans up only its own `corplex-ci` test project. Adding the workflow does not establish that GitHub Actions has executed/passed; inspect the actual run after pushing.
