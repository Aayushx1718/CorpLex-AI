# Verification record

This document describes what was actually exercised during the remaining-work implementation. It is not a security certification or a claim that hosted/public services were deployed.

- The full backend suite completed **75 tests**, and the frontend suite completed **21 tests**. Real PostgreSQL tests cover ingestion, analytical totals, scoped research/citation persistence, abstention, explicit scenario formulas, version comparison, workflow replay, reviewer authorization and transactional review rollback. Existing ML tests still distinguish synthetic test fits from the recorded CUAD benchmark.
- Frontend tests cover health, analytics, ingestion, ML status, research scope, exact scenario strings, review/export state and in-memory access-token handling. The production frontend build completes with lazy-loaded workbench/chart bundles.
- Twelve frozen, original synthetic research questions compare lexical, local latent and hybrid retrieval. All eight answerable cases have gold evidence in the top three; all four unsupported/hostile cases abstain, with exact quotes. This tiny set does not establish real-world quality or a hybrid advantage. Hosted generation was not evaluated against a real provider.
- Both Docker images were built with lockfile integrity/TLS verification retained. The cloud build needed the provided proxy and CA via supported proxy arguments/BuildKit secrets. Startup initially exposed restrictive copied-file permissions; explicit ownership fixed it while retaining non-root users. All app-stack containers then reported healthy.
- Chromium against the actual Docker reverse proxy exercised two uploaded versions, historical exact citations, unsupported-question abstention, a capped scenario, text comparison, approval-blocked export, explicit term/report approval, report download, audit history and mobile overflow checks.
- A separate random-name protected-mode stack used generated in-memory test tokens and a nondefault database password. It verified unauthenticated 401, authorized access/upload, reviewer 403/200, approval-gated export and origin rejection. Only its own test stack was stopped; no user document volume was deleted.
- `npm audit --omit=dev --audit-level=high` reported zero production dependency vulnerabilities at this run. This excludes development packages, Python/image vulnerability scanning and future advisories; those remain release checks.
- GitHub Actions configuration was added, but a remote Actions pass must be checked after the workflow actually runs. Local success does not prove remote CI, public deployment, snapshot restoration or live hosted-LLM quality.

## Navigation and recovery follow-up

- Workspace navigation now renders one page at a time, with active sidebar state, direct links and browser Back/Forward. The frontend suite passed **23 tests** and the production build passed after this change.
- The backend suite passed **78 tests** after adding recovery and the provider-check CLI. Provider-check tests cover no-key/no-request behavior, synthetic-only inputs, required abstention and redacted error output; these are not live provider results.
- The new recovery service backed up the running demo database and restored it into an isolated temporary database. Validation passed with 1 contract, 2 versions/source documents, 10 clauses, 6 obligations, 2 research answers, 1 scenario, 1 workflow and 7 audit events. Original byte hashes and source offsets matched. The live application database was not overwritten.
- Prior core implementation CI passed at commit `7ebbd28` (GitHub Actions run 40183341015). The new recovery CI step still requires its own remote execution after push; earlier results do not validate the new step.

- Recovery negative checks rejected both a modified archive (checksum mismatch) and a valid-checksum archive containing intentionally invalid clause offsets. Both used isolated copies of synthetic demo data.
