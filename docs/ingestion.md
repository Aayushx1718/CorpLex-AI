# Phase 2 — document ingestion

## Implemented flow

1. Limit the whole multipart request to 10 MiB + 64 KiB, including chunked requests; the file itself may not exceed 10 MiB. Require a supported user-selected contract type and a PDF/DOCX extension, matching MIME (or generic octet-stream) and file signature. Title and filename lengths are bounded. Filenames are display metadata only, never filesystem paths.
2. Run pypdf / python-docx in a separate process. Parsing has a 15-second wall timeout; Linux also enforces a 512 MiB address-space limit and 10 CPU seconds. At most two parsers run concurrently per API process; additional requests return 503 for retry. These limits protect availability but do not replace a hardened container sandbox or authentication.
3. PDFs are limited to 100 pages. DOCX packages must have valid structure and bounded ZIP expansion (30 MiB, 1,000 entries, maximum 200:1 per-entry ratio); duplicate/traversal entries, encrypted archives and macros are rejected. No archive files are extracted to disk.
4. Normalize line endings and trim source blocks, retaining one canonical Unicode text plus page (PDF) or body paragraph/table (DOCX) ranges. Output is capped at one million characters and 10,000 blocks, clauses and entities each. Source offsets refer to this canonical text, never to PDF bytes or rendered DOCX pagination. Clauses can span source units; the UI displays all overlapping units.
5. Extract numbered clause candidates, preserving any preamble; fall back to source blocks when no numbered headings exist. Extract ISO dates, explicit uppercase currency codes (USD/EUR/GBP/INR/CAD/AUD/JPY/CHF) with decimal amounts, and parties from a supported single-line `Parties: A and B` header. Invalid ISO dates or reversed explicit effective/expiration dates reject the upload. These are narrow, transparent rules, not comprehensive legal entity recognition.
6. Create source-linked obligation candidates for supported payment/termination/penalty/renewal/notice clauses. All remain `pending`. Multiple monetary mentions remain separate entity records and do not get collapsed into one obligation amount. Relative deadlines are preserved in the clause text, not guessed into calendar dates; monthly recurrence is detected conservatively. Monetary JSON values are strings to preserve decimal precision.
7. Within one PostgreSQL transaction, lock the content hash, resolve a duplicate or lock an existing contract to allocate a new version, then save original bytes, source text, metadata, warnings, entities, parties, clauses, obligation candidates and an audit event. Parsing/validation failures write nothing. Database failures roll back all writes, including original bytes; there are no external storage files to orphan. The unique SHA-256 constraint and advisory lock protect concurrent duplicate uploads. Contract-row locks serialize changed versions.

`validated` is a structural processing state. It does not mean legally approved, complete or accurate. The UI explicitly distinguishes candidates from approved obligations. No human approval endpoint, legal recommendations, financial loss estimates or ML predictions are implemented here.

## API behavior

- New upload: 201, `{ "duplicate": false, "document": ... }`.
- Byte-identical repeat: 200, same document ID and `duplicate: true`.
- Existing hash assigned to another requested contract/type: 409.
- Nonexistent version target / document: 404.
- Invalid file/type/date/form: 422; oversized request/file: 413.
- Parser capacity or database unavailable: 503; no partial records persist.
- Contract listing selects the latest ingested version and supports bounded limit/offset pagination. Document detail retains every version's evidence; older version IDs remain inspectable by API.

A title supplied for a duplicate or version does not rename its parent contract. SHA-256 deduplication is byte-level: re-exporting the same wording can produce different bytes and a distinct document. Cross-contract semantic deduplication and comparison are later work. Parties are linked per source and are not merged by unverified name similarity.

## Storage and migration

Run `bash scripts/init-db.sh` after `docker compose up -d --wait db`. The existing Phase 1 schema is preserved. `002_ingestion.sql` adds two tables under a transaction and advisory lock and can be rerun safely. This narrowly scoped additive migration is not a general migration framework; introduce Alembic before modifying populated tables.

Original content is private PostgreSQL `bytea`, with a `db:<uuid>` storage key. Source inspection excludes the original byte field and internal storage key. Original files are never served or opened in the browser. A future object-storage adapter can replace this storage boundary when document volumes justify it. The database volume needs backups; source documents do not live in the Git checkout.

## Tests and fixtures

From the repository root, generate fixtures with `backend/.venv/bin/python scripts/generate_samples.py`. `samples/contracts/expected.json` records explicit ground truth amounts and lifecycle dates. The generator creates eight synthetic files in ignored `samples/generated/`. ReportLab is used only for test/sample PDF generation. No external data, LLM provider or credential is required.

For an end-to-end check with the API and Vite running, execute `backend/.venv/bin/python scripts/smoke_ingestion.py`. It creates/reuses only the generated synthetic vendor record, then verifies persisted evidence and repeat-upload behavior.

Run the unit suite with `backend/.venv/bin/pytest backend/tests`. PostgreSQL integration tests deliberately skip unless `TEST_DATABASE_URL` is provided; this must not be described as a full integration pass. To run everything against the default local development PostgreSQL instance:

```bash
TEST_DATABASE_URL=postgresql+psycopg://corplex:corplex_local@localhost:5432/corplex \
  backend/.venv/bin/pytest backend/tests
npm test --prefix frontend
npm run build --prefix frontend
```

Integration tests create random, disposable PostgreSQL schemas, apply both SQL files, exercise actual API multipart requests and transactions, then drop only their own schemas. The test database user needs schema-creation permission. Tests cover upload round trips, exact evidence ranges, both file formats/all contract types, image-only/encrypted PDF rejection, malformed files, ZIP expansion, oversize and chunked requests, invalid dates, table order, concurrent duplicates, versioning, conflict/not-found responses and simulated mid-transaction failure. Frontend tests cover upload, duplicates, failures and existing-version selection.

## Known limitations

- No OCR; image-only documents fail with an actionable message. Mixed PDFs retain warnings for textless pages. Nonempty extraction cannot prove a page is complete.
- Reading order, tables, multi-column PDFs, wrapped party headers, non-ISO dates, implicit currencies and complex clause numbering require further extraction work. DOCX headers, footers, images and text boxes are omitted and flagged; nested table layout is not reconstructed.
- Current extraction uses deterministic heuristics and a small synthetic fixture set. Passing these fixtures is not real-world extraction accuracy or legal validation.
- Upload is synchronous and intended for trusted local development. Durable jobs, antivirus scanning, broader parser isolation, authentication/authorization, retention controls and public deployment remain release work. Do not upload confidential documents or expose the development server publicly.
