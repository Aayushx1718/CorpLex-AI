# CorpLex AI

Corporate contract intelligence and financial risk analytics. **Phase 3 analytics**: a working FastAPI service, React/TypeScript/Tailwind upload workspace, PostgreSQL storage, deterministic PDF/DOCX extraction, SQL-backed interactive analytics and original synthetic contracts. ML, RAG and agents remain planned. Decision-support information only; not legal advice.

## Run locally

Prerequisites: Python 3.12, uv, Node.js 24/npm, Docker with Compose v2. Commands start from the repository root. Local database credentials below are development defaults, not production credentials.

```bash
cp -n .env.example .env
UV_CACHE_DIR=/tmp/corplex-uv-cache uv sync --project backend --frozen
npm ci --prefix frontend --cache /tmp/corplex-npm-cache
docker compose up -d --wait db
bash scripts/init-db.sh
```

Use two terminals:

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev
```

Open the Vite address printed in your local terminal. It proxies `/api` to port 8000. `GET /api/health` returns `{"status":"ok","service":"corplex-api"}`. `GET /api/ready` returns `ready` only when PostgreSQL and the schema are available; otherwise HTTP 503. FastAPI OpenAPI docs are served at `/docs` on the API. The web API card reflects liveness, not database readiness.

Run verification from the root:

```bash
# Unit suite (PostgreSQL integration tests skip without TEST_DATABASE_URL)
(cd backend && .venv/bin/pytest)
# Full suite, including isolated-schema PostgreSQL tests; substitute your local DB URL if changed
TEST_DATABASE_URL=postgresql+psycopg://corplex:corplex_local@localhost:5432/corplex backend/.venv/bin/pytest backend/tests
npm test --prefix frontend
npm run build --prefix frontend
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/ready
curl --fail http://127.0.0.1:5173/api/health
```

Stop terminal servers with Ctrl-C; `docker compose stop db` stops the database without deleting data. The initialization script bootstraps the initial schema if absent, then applies the repeatable additive ingestion and analytics migrations. Existing contract data is preserved; future migrations require review. Do not use `down -v` on data you need. If ports conflict, stop only your own processes or configure alternate ports and update the Vite proxy/database URL together.

## Configuration

`.env` is ignored. Settings are loaded relative to `backend/`, so start the API there. `DATABASE_URL` uses SQLAlchemy's psycopg dialect. `CORS_ORIGINS` is a JSON list. Vite's proxy keeps development requests same-origin. No LLM credentials are needed in Phases 1–2. Never commit API keys or confidential contracts. Changing PostgreSQL credentials on an existing volume requires a database password change; editing `.env` alone does not update that database.

## Design and next steps

- [Architecture and folders](docs/architecture.md)
- [Portfolio analytics and metric definitions](docs/analytics.md)
- [Database schema and constraints](docs/schema.md)
- [Datasets, labeling limitations and evaluation](docs/datasets.md)
- [Phased implementation plan and acceptance gates](docs/plan.md)
- [Synthetic sample provenance](samples/contracts/README.md)

The foundation runs on the host with PostgreSQL in Docker. Full application images, production security, a migration framework and cloud deployment are future release work. Do not expose this local development foundation publicly.

## Upload and verify a synthetic contract

Generate all eight PDF/DOCX samples from the original text fixtures (ReportLab is a development-only dependency):

```bash
backend/.venv/bin/python scripts/generate_samples.py
curl --fail -F 'contract_type=vendor' -F 'title=Synthetic vendor' \
  -F 'file=@samples/generated/vendor.docx' http://127.0.0.1:8000/api/contracts
```

With both servers running, `backend/.venv/bin/python scripts/smoke_ingestion.py` verifies the live proxy, stored source evidence and duplicate behavior using the generated vendor fixture. It creates a synthetic demo record if not already present.

Or use **Contract repository → Upload and extract** in the frontend. Inspect entities, clauses and their source ranges. Repeat the same upload: the API returns HTTP 200 with `duplicate: true` and the same document ID. New content returns HTTP 201. Select an existing contract as the version target (or pass `contract_id` in the multipart form) to store changed bytes as the next version. Type must match the existing contract. Titles apply only to new contracts. Deduplication is byte-identical SHA-256, not semantic similarity; content already assigned to another contract/type returns 409.

- `GET /api/contracts?limit=25&offset=0`: paginated agreements with their latest ingested version.
- `GET /api/documents/{id}`: canonical extracted text, source units, clauses, entities and pending obligation candidates.
- `POST /api/contracts`: multipart `file`, `contract_type`, optional `title` / `contract_id`.

Upload constraints and extraction limitations are documented in [Phase 2 ingestion](docs/ingestion.md). OCR and human approval are not implemented. The database holds original bytes atomically with extracted records; no raw-document download endpoint is exposed. Back up the PostgreSQL volume to retain uploads; do not assume environment snapshots preserve an external Docker daemon's volumes.

## Portfolio analytics

Use **Portfolio analytics** to filter by agreement type, currency, review state and deadline window. The dashboard shows latest-version KPIs, interactive count charts, exact amount groups, agreement source links and recorded deadlines. Uploading a document refreshes the dashboard. No data is fabricated for empty portfolios. See [metric definitions and SQL design](docs/analytics.md) before interpreting amounts; they are stated terms, not estimates of exposure or losses.

```bash
curl --fail 'http://127.0.0.1:8000/api/analytics/overview?as_of=2026-03-01&contract_type=vendor'
```
