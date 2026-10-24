# Phase 3 — SQL analytics and dashboard

## Run

Start PostgreSQL, apply migrations, then run the backend and frontend as described in README.md. `bash scripts/init-db.sh` now applies `003_analytics.sql` after the existing schemas without deleting records. The migration creates/replaces three read-only views under a transaction and advisory lock. Upload synthetic contracts in the repository UI, then inspect **Portfolio analytics**. Analytics refreshes after upload; the Refresh button also updates data changed elsewhere.

`GET /api/analytics/overview` returns the same facts as the dashboard. Optional query parameters:

| Parameter | Meaning |
| --- | --- |
| `contract_type` | nda / employment / vendor / service; absent means all |
| `currency` | Uppercase three-letter code; filters matching obligation facts, not currency conversion |
| `review_status` | pending / approved / rejected; absent means all states |
| `as_of` | ISO date; absent uses the UTC calendar date |
| `horizon_days` | Inclusive future window through as_of + days; 1–365, default 90 |
| `limit`, `offset` | Agreement-register pagination, default 20/0, maximum page size 100; does not limit KPI/chart totals |

Example: `/api/analytics/overview?contract_type=vendor&currency=USD&review_status=pending&as_of=2026-03-01&horizon_days=90`.

## Metric definitions

- Agreements: latest structurally validated, ingested version per logical contract; not an active-contract count. Contracts without obligations remain visible when no obligation filters are selected.
- Currency and review filters restrict the agreement population to contracts with at least one obligation matching both filters. Only matching obligations contribute to obligation metrics. All panels share this scope.
- Obligation candidates / pending review: row counts, not risk scores or financial exposure. Rejected facts remain in all-state counts but are labeled separately in charts and amount groups.
- Stated single-amount terms: exact decimal sums of non-null obligation amounts, grouped by currency, clause kind, recurrence and review state. Null recurrence means **unspecified**, not one-time. These sums do not annualize, infer outstanding balances, resolve caps/rates or represent contract value, loss or exposure. Raw monetary mentions are not summed. No cross-currency grand total exists.
- Expiring in window: recorded contract expiration dates from as_of through the end date, inclusive. This is not the renewal-notice deadline. Missing expiration dates remain explicit.
- Past recorded due dates: non-rejected obligation dates before as_of. The schema has no settlement status; a past date does **not** prove a payment is unpaid. The tracker includes all past obligation due dates plus future dates through the window end.
- Missing due dates: matching obligations whose due_date is null. Ingestion currently preserves relative deadlines in source text but does not resolve them into calendar dates. The tracker will therefore commonly show expirations only after uploading existing samples.
- Deadline tracker: non-rejected obligation dates and scoped contract expirations. At most the earliest 100 events are returned, with `deadline_total` exposing truncation; narrow filters to inspect other scopes. Rejected obligations never contribute to this tracker, even when the review filter is rejected. Contract expirations still apply to scoped agreements.
- Party names: source-extracted names. Roles/identities are unverified; a vendor-type filter supports vendor-agreement analysis without claiming every named party is the vendor. Cross-contract entity resolution is not implemented.

## SQL design

`analytics_latest_documents` uses a CTE and `ROW_NUMBER() OVER (PARTITION BY contract_id ORDER BY version_number DESC)` to select a version before joining clauses/obligations. `analytics_obligations` exposes latest-version facts only. `analytics_contract_parties` aggregates distinct names independently of obligation facts. API queries use parameterized filters, scoped/facts CTEs, filtered aggregates and joins to per-contract counts. This avoids the classic parties × obligations multiplication error.

All response queries run in one PostgreSQL REPEATABLE READ transaction: KPIs, groups, register and tracker describe the same snapshot even if ingestion runs concurrently. Pagination changes only register rows. SQL numeric values are emitted as strings; financial values never pass through JavaScript floating-point calculations. Count charts use Recharts; exact amount groups use a table. The chart workspace is loaded separately so its dependencies do not inflate the initial application bundle.

These views are live, not materialized. Indexes and source primary/foreign keys support joins; benchmark real volumes before adding caching, incremental pipelines or materialization. API failure responses expose neither SQL text nor credentials.

## Verification

The real PostgreSQL suite uses isolated disposable schemas. An independently specified fixture has four contracts, two vendor versions, two parties on the latest vendor version, pending/approved/rejected terms and multiple currencies/recurrences. Expected current counts are four agreements, six obligations and four pending terms. The monthly USD sum is exactly 100 + 200 = 300, excluding the old version's 9999 and avoiding multiplication by two parties. EUR and GBP stay separate. Other cases cover no data, filters, missing dates, inclusive boundaries, pagination, exact large decimals, missing migrations and explicit deadline truncation.

Frontend tests cover precision-preserving tables, filter requests, refresh after ingestion, empty/error states, source callbacks and pagination. Chromium smoke checks exercise actual Recharts rendering, SQL-backed filters, source inspection and mobile overflow. Run the complete backend and frontend checks from README.md; integration cases skip unless TEST_DATABASE_URL is set, so distinguish skipped runs from full verification.

## Remaining scope

No new approval workflow, date editor, FX rates, vendor identity resolution, ML classification, RAG or scenario engine was added in this phase. Review-state/date test fixtures exercise stored database fields; uploading a document still creates only pending obligation candidates. Production authentication, query budgets and operational hardening remain release gates.
