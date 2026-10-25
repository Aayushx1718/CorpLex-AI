# Financial scenarios and comparison (Phase 6)

## Explicit financial what-if scenarios

`POST /api/finance/scenarios` accepts one source document version, one currency and up to twenty unique source obligation IDs. Each line specifies quantity, optional assumed rate, optional explicit cap and an assumption note. A single extracted amount is the default rate. A clause with multiple monetary mentions has no inferred single amount and therefore requires an explicit rate assumption. Recurrence, future service duration, cap applicability and exchange rates are never silently inferred.

Formula: `sum(min(rate × quantity, cap))` where a cap is explicitly provided, otherwise `sum(rate × quantity)`. Decimal arithmetic uses precision 50 and each line is rounded to four decimal places using half-even rounding before summation. Results remain strings through the API/UI. Totals must fit PostgreSQL numeric(20,4). Currency mismatches, repeated obligations, rejected sources, wrong-document IDs and nonfinite/negative inputs are rejected. Pending terms require `include_unreviewed: true`; quantity/cap/rate overrides or pending sources require an explanatory note.

Example: an extracted USD 100.1250 rate × quantity 3 = USD 300.3750. With a user-entered cap of USD 250.00, the hypothetical result is USD 250.0000. This is not a measured loss, annualized contract value, outstanding balance or legal determination. The engine does not prove that the user's assumptions, rate or cap are legally applicable.

Scenarios persist original source text, source review state, formula version, exact inputs, line results, currency and the user's assumption note in PostgreSQL. `GET /api/finance/scenarios/{id}` retrieves that saved scenario. Later reviews do not rewrite its original assumptions/history. Audit events record creation without dumping contract content or secrets into logs.

## Cross-contract / version comparison

`POST /api/comparison` takes two distinct stored document-version IDs. It supports versions of one agreement or separate agreements. Source text is limited to 100,000 characters and 200 clauses per side to bound work.

Word/bigram TF-IDF cosine similarity greedily aligns clauses one-to-one at a declared .20 threshold. Whitespace-normalized exact matches are unchanged; others are modified; similarity >=.90 is labeled lexical near-duplication. Unmatched clauses remain explicitly left-only or right-only. Unified source diffs are limited to 2,000 displayed lines with a truncation flag. Candidate obligation terms are returned separately for review.

These thresholds are heuristics, not learned legal-conflict detection. Different prices, currencies, dates or clauses do not automatically imply contradictory obligations. The interface displays source text/differences and explicitly requires human interpretation. Cross-contract company/role resolution, applicability logic and expert conflict adjudication remain outside this implementation.

## Checks

Real PostgreSQL tests compare exact hand-calculated scenario results, cap handling, currency rejection, pending acknowledgment, missing/ambiguous rates, duplicate prevention, persistence and version differences. Browser checks exercise the same operations through the workbench. No arbitrary financial risk score is presented as a trained prediction.
