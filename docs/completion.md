# Completion status

The local portfolio application implements the seven planned phases within the evidence and safety limits described below. Visual redesign is deferred. “Implemented” does not mean certified for legal decisions or production deployment.

| Capability | Current state | Remaining limit |
| --- | --- | --- |
| PDF/DOCX ingestion and versioning | Implemented and tested with original source bytes and offsets | Scanned PDFs require a separate OCR feature |
| SQL analytics and filters | Implemented and tested | Amounts are extracted terms, not estimates of legal loss |
| Five-class CUAD clause classifier | Benchmark, training/activation pipeline, SHAP and lab implemented | Fresh Docker clones need optional ML dependencies and a trusted locally trained artifact for inference |
| Contract research | Local retrieval, exact citations, abstention and optional hosted quote selection implemented | An opt-in synthetic live-check CLI is included; real provider validation needs a securely configured API key; the small synthetic evaluation is not real-world QA accuracy |
| Financial scenarios and comparison | Implemented and tested | Explicit assumptions and textual differences require human interpretation |
| LangGraph workflow and review | Persistent reports, human decisions, approval-gated export and audit implemented | Local reviewer names are unverified; shared tokens are not individual user/tenant identity |
| Laptop deployment | Docker stack verified and running on the user's laptop | Keep default unauthenticated mode local |
| Backup and recovery | Backup/checksum plus isolated restore and source integrity checks implemented | User must choose protected storage, run backups, set retention and perform a reviewed live recovery switch |
| Public portfolio demo | Not deployed | Hosting account and a verified current free-tier plan are required; do not expose the local development stack |
| Business-risk severity model | Not available | Requires licensed expert risk labels, annotation agreement and separate validation; clause labels cannot substitute |

## Current agreed scope: free local application

The user has chosen a local application with no domain, public hosting, paid API or resume-presentation deliverables. Hosted validation and public deployment are optional future work, not completion blockers for this scope. The interface now provides a local entry flow, live graphical dashboard, separate tool pages and a final System status page. See [interface.md](interface.md). Individual user accounts remain separate from the explicitly labelled local entry flow.

## Optional external steps before claiming a full hosted release

1. Configure `CORPLEX_LLM_API_KEY` securely on the backend and validate real supported/unsupported questions with the selected model. Never put the key in chat, source, screenshots or the frontend. Hosted calls may incur provider usage charges.
2. Choose and provision the previously requested free public demo using current verified host limits. Configure TLS, distinct access/reviewer tokens, allowed hosts/origins and a private database. Verify persistence/restart behavior and disclose any free-tier expiration or sleep limits. No host or paid service has been created.
3. For use beyond a portfolio, complete individual identity/authorization, tenant isolation, managed secret rotation, backup/restore drills and retention policy, independent security review and expert legal/model review.

The code supports a local demonstration now; missing external credentials, deployment and expert labels must not be reported as completed. See verification.md for executed checks, deployment.md for startup and recovery.md for backup commands.
