# CorpLex AI

Corporate contract intelligence and financial risk analytics. The portfolio now includes document ingestion, SQL analytics, evaluated clause-type ML, cited research, explicit what-if scenarios, version comparison and human-reviewed LangGraph reports. **No validated business-risk severity model or autonomous legal decision maker is claimed.** Hosted LLM evidence selection is implemented but awaits a secure provider key and live validation.

## Quickest way to see the app

With Git and Docker Desktop installed and running, clone this repository and run:

```bash
docker compose -p corplex-app -f compose.app.yaml up --build -d --wait
```

The interface runs on your computer's loopback port **8080**. This container option does not require host Python, Node or uv. It includes the source-backed tools and recorded ML benchmark results; classification additionally requires the optional ML dependencies and trusted trained artifact. See [deployment and Windows instructions](docs/deployment.md).

## Run locally

Prerequisites: Python 3.12, uv, Node.js 24/npm, Docker with Compose v2. Commands start from the repository root. Local database credentials below are development defaults, not production credentials.

```bash
cp -n .env.example .env
UV_CACHE_DIR=/tmp/corplex-uv-cache uv sync --project backend --frozen --group ml
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

`.env` is ignored. Settings are loaded relative to `backend/`, so start the API there. `DATABASE_URL` uses SQLAlchemy's psycopg dialect. `CORS_ORIGINS` is a JSON list. Vite's proxy keeps development requests same-origin. Local research, ingestion and analytics need no LLM credentials. Never commit API keys or confidential contracts. Changing PostgreSQL credentials on an existing volume requires a database password change; editing `.env` alone does not update that database.

## Design and next steps

- [Backup and recovery](docs/recovery.md)
- [Completion status and external release gates](docs/completion.md)
- [Contract research and hosted setup](docs/research.md)
- [Financial scenarios and comparison](docs/financial-comparison.md)
- [Workflow approvals and access controls](docs/workflows-security.md)
- [Architecture and folders](docs/architecture.md)
- [ML preparation, license gate and experiment workflow](docs/ml/README.md)
- [Portfolio analytics and metric definitions](docs/analytics.md)
- [Database schema and constraints](docs/schema.md)
- [Datasets, labeling limitations and evaluation](docs/datasets.md)
- [Phased implementation plan and acceptance gates](docs/plan.md)
- [Synthetic sample provenance](samples/contracts/README.md)

Host development and a non-root Docker application stack are supported. Access/reviewer token gates, data-preserving migrations and CI are implemented. Public cloud deployment, per-user identity/tenant controls and production/legal review remain external release work; see docs/workflows-security.md.

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

Upload constraints and extraction limitations are documented in [Phase 2 ingestion](docs/ingestion.md). OCR is not implemented; extracted obligations can be reviewed through the workflow tools. The database holds original bytes atomically with extracted records; no raw-document download endpoint is exposed. Back up the PostgreSQL volume to retain uploads; do not assume environment snapshots preserve an external Docker daemon's volumes.

## Portfolio analytics

Use **Portfolio analytics** to filter by agreement type, currency, review state and deadline window. The dashboard shows latest-version KPIs, interactive count charts, exact amount groups, agreement source links and recorded deadlines. Uploading a document refreshes the dashboard. No data is fabricated for empty portfolios. See [metric definitions and SQL design](docs/analytics.md) before interpreting amounts; they are stated terms, not estimates of exposure or losses.

```bash
curl --fail 'http://127.0.0.1:8000/api/analytics/overview?as_of=2026-03-01&contract_type=vendor'
```

## Clause-type model status

The machine learning lab displays real dataset provenance, held-out comparisons, per-class performance, confusion matrices and SHAP explanations. License verification succeeded using the official CUAD dataset card. Validation selected Logistic Regression; its test macro F1 is **0.9479 on 361 positive gold spans across five categories**. This is not a full-contract extraction score or a validated legal-risk model. See [the ML workflow and full experiment report](docs/ml/README.md).

The classifier is active in the current cloud filesystem. Raw data and trained pickle artifacts are excluded from Git; a fresh clone must fetch/prepare the pinned release, verify its license, train and review/activate an artifact using the documented commands. Install the optional `ml` group for these operations and the full ML test suite. Without the group, ingestion and analytics remain supported but optional ML tests skip.

## Intelligence workbench

- **Contract research:** choose all latest agreements or an explicit source version, ask a question and inspect exact quotations. Local mode needs no key. Hosted mode requires `CORPLEX_LLM_API_KEY` in secure backend settings; the browser never receives it. It sends selected excerpts to the provider only when that mode is chosen. Unsupported questions abstain.
- **What-if scenarios:** select a source obligation, quantity, optional assumed rate/cap and a meaningful assumption note. Pending sources require explicit acknowledgment. Currency totals never mix, and hypothetical amounts are not represented as losses.
- **Compare versions:** select two stored versions and inspect matched/changed/unmatched clauses and the source diff. Textual differences are not automatically legal conflicts.
- **Review workflow:** generate a six-step LangGraph report, inspect source evidence, record a human decision and optionally approve individual extracted terms. Export is blocked until report approval. Local names are unverified; production review requires a separate reviewer token.
- **Audit log:** inspect stored application events. It is not a tamper-proof regulatory ledger.

Reproduce the small synthetic retrieval check with `backend/.venv/bin/python scripts/evaluate_research.py`. Run the optional protected-container smoke check with `backend/.venv/bin/python scripts/check_protected_stack.py` after building images and generating samples; it creates/stops only its own random-name test project on port 8081. It never prints generated test tokens.

For shared operation, configure strong distinct workspace/reviewer tokens and a nondefault database password; `APP_ENV=production` refuses insecure defaults. Tokens belong in ignored local/runtime configuration, never in Git. The default local demonstration has no authentication and must not be exposed publicly. See the release limits before claiming production readiness.
