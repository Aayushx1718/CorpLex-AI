# Architecture and scope

The repository was empty (unborn `work` branch, no tracked files or remote refs) at inspection. Phase 1 established the foundation; Phases 2–3 add deterministic ingestion and SQL-backed analytics, with a five-category clause-type model added in Phase 4; later AI features remain pending.

## Components

React + TypeScript + Tailwind → Vite `/api` proxy → FastAPI / Pydantic → SQLAlchemy / psycopg → PostgreSQL 17.

The frontend calls a real API health endpoint. Liveness does not depend on PostgreSQL; readiness checks that PostgreSQL and the Phase 3 analytics view are available. Contract upload/list, source inspection and portfolio analytics endpoints are implemented. Recharts renders live type/kind counts; exact financial term groups use precision-preserving tables.

Phase 4 preparation adds optional offline clause-type experiments and a trusted local artifact boundary; license verification succeeded and the reviewed validation-selected classifier is active locally. Later phases add hybrid retrieval with FAISS or Chroma, and finally LangGraph orchestration. No trained risk model is currently available. Install those dependencies only when their phase needs them. PostgreSQL remains the source of truth; vector indexes are rebuildable derived artifacts. Current uploads use synchronous request handlers with resource-bounded parser subprocesses. A durable background job queue is deferred until workloads require one.

## Folder structure

- `backend/app/`: settings, API and subsequent domain services.
- `backend/tests/`: API, extraction, PostgreSQL integration and gated ML tests.
- `frontend/src/`: React workspace, styles and component tests.
- `db/`: normalized bootstrap schema and additive ingestion/analytics migrations, no seeded claims.
- `samples/contracts/`: original synthetic demonstration contracts and provenance.
- `docs/`: architecture, schema decisions, datasets and acceptance criteria.
- `compose.yaml`: local PostgreSQL with persistent storage and health check.

## Data flow and safeguards

Phase 2: bounded upload → resource-bounded extraction and validation → hash and contract locks → atomic PostgreSQL transaction storing original bytes, source text, metadata, entities, versions and clauses/obligation candidates → reviewable source inspection. No external files can be orphaned by a failed transaction. Human approval remains future work. PDFs use pages; DOCX uses paragraph/character anchors because page boundaries depend on rendering. Scanned PDF OCR is a separately measured capability.

No generic risk score is presented as a learned probability. Annotations, model predictions and financial scenarios are separate entities. Every later answer must cite stored source chunks; unanswerable questions must abstain. Consequential recommendations require explicit human approval. Authentication, authorization, retention, stronger container isolation and audit protections are Phase 7 release gates; this foundation is for trusted local development only. Do not upload confidential contracts.

## Reproducibility

Python dependencies are pinned by `backend/uv.lock`; JavaScript dependencies by `frontend/package-lock.json`. Use Python 3.12, Node 24, uv and Docker Compose v2. PostgreSQL uses a fixed version tag. For deployment, pin container digests and build tested API/web images in Phase 7. Current Docker support intentionally covers the database, not a production deployment.
