# PostgreSQL schema

The executable definitions are `db/001_initial.sql` and the repeatable additive migrations `db/002_ingestion.sql` and `db/003_analytics.sql`, plus `db/004_workbench.sql`. UUIDs identify domain entities; timestamps are UTC-aware. Money uses exact `numeric`, never binary floating point. Currency is explicit and totals must not combine currencies without a documented exchange-rate source and date.

| Table | Responsibility / relationships |
| --- | --- |
| contracts | Stable logical agreement identity and supported contract type |
| document_versions | Immutable source versions; contract FK; unique content hash and per-contract version; storage reference and lifecycle dates |
| document_sources | Original private bytes, canonical extracted text, page/paragraph/table anchors, metadata, warnings and extractor version; one-to-one with document_versions |
| document_entities | Source-backed party/date/money mentions with normalized values and exact text offsets |
| parties / contract_parties | Legal entities and roles on each version; many-to-many |
| clauses | Source text, extractor version, ordinal, optional PDF page and character offsets per document version |
| obligations | Clause-backed payments, penalties, termination, renewal and notice terms; amount/currency pair, due date, review state |
| clause_annotations | Human labels, rationale, annotator and rubric version; training evidence |
| model_runs | Versioned artifacts, dataset, split manifest and evaluation metrics |
| risk_predictions | Clause and model-run FK, predicted class, probability and explanation; separate from human labels |
| retrieval_chunks | Clause-backed text spans plus embedding/index versions and external vector key |
| research_answers / answer_citations | Generated answer provenance and exact quoted evidence tied to source chunks |
| exposure_scenarios / scenario_obligations | Formula version, explicit assumptions, currency/result and source obligation links |
| audit_events | Actor, action and entity references; no raw document text or secrets in details |

Constraints enforce version/hash uniqueness, allowed states, positive ranges and valid amount/currency pairs. Indexes cover common joins and approved obligation deadlines. Future ETL must additionally validate source offsets, currency membership, citation quotations and scenario/source consistency transactionally; SQL constraints alone cannot prove extracted legal meaning. Cross-document duplicates require explicit linking rather than silently assigning one uploaded hash to two contracts.

Phase 3 adds latest-document, latest-obligation and aggregated-party views for the analytics API; see analytics.md. Model outcomes and inferred renewal deadlines are not included. Avoid many-to-many join multiplication by pre-aggregating obligations before joining parties. Window functions rank latest document versions; CTEs expose each aggregation stage. No synthetic predictions are seeded.

This is a bootstrap schema plus repeatable additive migrations, not a general migration framework. The initialization script bootstraps when the contracts table is absent, then always applies the additive migration under an advisory lock. It preserves existing data. Introduce Alembic and an upgrade path before evolving a persisted database. Never delete a populated volume as an upgrade mechanism. Audit events need append-only database permissions and retention policies before deployment; the current table alone does not provide tamper resistance.


Phase 5–7 storage: `research_answers.details` retains mode/scope/index provenance; `answer_citations` references stable source chunks and exact quotations. `exposure_scenarios.assumptions` stores formula inputs, original source-review state and line results without later rewriting history. `workflow_runs` has one immutable-source-version report, an awaiting/approved/rejected state, reviewer metadata and a persistent export gate. Optional term reviews are constrained to that version and commit atomically with the report decision. Audit events record actions but are not tamper-proof database-owner-proof records.
