# Deterministic workflows, review and access controls (Phase 7)

## LangGraph coordination

Six named, deterministic functions run in sequence: Document Extraction, Clause Analysis, Risk Assessment, Financial Analysis, Retrieval and Report Generation. They read the already ingested immutable source version rather than invoking arbitrary tools or autonomous agents. Extraction/clauses preserve source evidence; risk emits only transparent text-match review cues, never a validated risk score; financial analysis does not invent loss totals; retrieval reports chunk provenance. No email, Slack, payment, deployment or legal action is triggered.

A source-version lock and unique database constraint make workflow creation replay-safe: repeat requests reopen the same report. Reports start at `awaiting_review`; no graph node can approve them. `POST /api/workflows/{id}/review` records an explicit approve/reject decision, reviewer name and substantive note. Optional per-obligation approvals are constrained to that source version and save atomically with the report decision. An invalid ID rolls back the entire review. Decisions are immutable; revised analysis requires a new source version. Rejected reports cannot change obligation reviews.

`GET /api/workflows/{id}/export` refuses export until the state is approved. Approval marks only the report and explicitly selected extracted terms; it does not establish legal enforceability, approve every obligation or validate a business-risk model. Historical versions remain labeled by version number. No consequential legal recommendation is generated or authorized by this workflow.

## Identity and tokens

Trusted local development defaults to no authentication and binds ports only to loopback. The UI clearly labels local reviewer names as **not identity-verified**. This is a demonstration review gate, not a compliance-grade identity assertion.

For protected operation set `CORPLEX_ACCESS_TOKEN` and a separate `CORPLEX_REVIEW_TOKEN`. All `/api/` routes except liveness and the nonsecret access-status endpoint require a bearer access token; review additionally requires the reviewer token in `X-Review-Token`. Token comparison is constant-time. Browser tokens stay in memory, never URLs/localStorage. Reviewer tokens are cleared after a decision. Token values are never returned by configuration/status routes or written to reports. Shared service tokens identify authorization capability, not an individual human; per-user SSO/RBAC is still needed for a multi-user production service.

`APP_ENV=production` refuses startup unless both tokens are distinct and at least 32 characters, the default database password is replaced, and wildcard CORS/host settings are absent. Allowed hosts default to localhost/127.0.0.1/backend; configure explicit `ALLOWED_HOSTS` for an actual domain. Mutating requests from unapproved cross-origin sites are rejected, including malformed origins. The reverse proxy preserves the original host. These checks supplement authentication; they do not replace TLS or tenant authorization.

## Isolation, privacy and limits

- File/request caps, ZIP expansion checks and bounded parser subprocesses remain in force. Originals stay in PostgreSQL and are not served as executable/downloadable uploads.
- Research/graphs disable LangSmith tracing. Hosted mode intentionally sends selected excerpts to the configured provider only when chosen; local mode has no provider call.
- Query and comparison scopes are bounded. Source text is escaped by React; no model HTML is inserted. Output quotes must exactly match stored sources.
- Container API and web processes use non-root identities, read-only root filesystems, tmpfs scratch space, dropped capabilities and no-new-privileges. PostgreSQL has a persistent named volume and no app-stack host port.
- Nginx sets CSP, no-sniff, frame-denial and referrer headers. The app-stack port is bound to 127.0.0.1; no public deployment is performed automatically.
- Audit events include ingestion, research, scenarios, workflow creation and review. `GET /api/workbench/audit` is access-controlled and paginated. They are application records, not append-only/tamper-proof regulatory logs; a database owner can alter them.

## Release limits

This is a portfolio/development application with deployable containers and safety checks, **not a declaration of production/legal readiness**. Public deployment still needs a chosen host/domain, TLS termination, managed secrets, database backup/restore testing, encryption/retention policies, per-user authorization/tenant boundaries, dependency/image vulnerability scanning, operational rate limits, incident monitoring and independent legal/security review. Do not upload confidential contracts into a publicly exposed demo. Hosted-provider calls remain unverified until a real secure API binding is supplied and exercised.
