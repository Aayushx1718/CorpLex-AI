# Source-grounded contract research (Phase 5)

The workbench can search stored contracts and return exact source quotations. Scope defaults to the latest structurally validated version per agreement; selecting document IDs can explicitly include historical versions. The server applies version/type filters **before** fitting retrieval features or building an index. It never falls back to another document when the selected scope is empty.

## Retrieval and citations

- Clauses are split into at most 900-character, word-aligned chunks with approximately 150-character overlap. Original canonical-text offsets are retained. Stable chunk UUIDs include the clause ID and chunking version.
- LangChain Documents/Embeddings and RunnableLambda coordinate local retrieval. Sparse word/bigram TF-IDF provides the lexical baseline. TruncatedSVD provides corpus-local LSA vectors and FAISS inner-product search. Hybrid retrieval uses reciprocal-rank fusion (constant 60).
- These local vectors are **not pretrained semantic embeddings**. Dense/lexical signals share corpus features, so hybrid gains must not be assumed. No model download or API key is needed for local retrieval. Scores are rankings, not probabilities or answer confidence.
- A lexical floor of .10 is a declared heuristic. Explicit governing-law/currency requests have conservative evidence checks. Hostile prompt patterns and requests for legal conclusions abstain. Unknown topics normally yield no evidence. This is not proof of complete semantic answerability or comprehensive prompt-injection defense.
- Citations retain source version, clause/chunk IDs, exact quotes, canonical character ranges and PDF page/DOCX body anchors. A clause/source mismatch fails with 409. Stored answer/citation records are written atomically; provider failure rolls back the operation.
- Research is limited to 2,000 chunks and two concurrent requests per API process. Oversized scopes must be narrowed; they are never silently truncated. LangSmith tracing is explicitly disabled for research and workflows to avoid exporting documents through telemetry.

## Answer modes

**Local** returns relevant source excerpts with numbered citations. It is deterministic extractive retrieval, not LLM generation or a legal conclusion.

**Hosted** calls OpenAI's Responses API to select exact quotations from the retrieved context. Structured JSON-schema output is requested. The model receives the question and up to four retrieved chunks; it must treat contract content as untrusted data. The server accepts only known chunk IDs and exact nonempty source substrings. It composes the displayed answer itself from those quotations. Free-form model claims, invented sources, malformed outputs and provider error bodies never become an answer. A valid quote can still be irrelevant or incomplete: human review and broader relevance evaluation remain necessary.

The user opted into hosted generation. Configure `CORPLEX_LLM_API_KEY` securely and optionally `CORPLEX_LLM_MODEL` (default `gpt-4.1-mini`). The secret requirement and `api.openai.com` destination have been saved in environment settings. Never put a real key in Git, chat, a URL or a browser field. Only the backend calls the provider. Missing credentials return 503 and leave local mode available. TLS verification and a 30-second timeout remain enabled.

**Current verification boundary:** no provider credential was available when this phase was implemented. Citation rejection and successful response handling can be tested with mocked provider responses, but a live hosted answer is not claimed until the configured key is available and that operation is exercised.

## API

- `GET /api/research/status`: local availability, hosted configuration presence (never secret values), model and answer policy.
- `POST /api/research/ask`: `question`, optional `document_ids` (maximum ten), optional `contract_type`, `retrieval_mode` (`lexical`, `dense`, `hybrid`), `answer_mode` (`local`, `hosted`).

Empty/unanswerable scopes return an explicit abstention without citations. Backend errors and missing credentials are distinct from abstention; failed provider calls are not disguised as successful local generation.

## Evaluation

Run `backend/.venv/bin/python scripts/evaluate_research.py`. The frozen CC0 fixture in `samples/contracts/research-evaluation.json` has three original synthetic documents, eight answerable questions and four unsupported/hostile questions. Gold evidence is independently specified as source substrings. The script compares lexical, local dense and hybrid retrieval and writes `docs/research-evaluation.json` with recall@3, MRR@3, exact quote rate and abstention results.

This small set tests mechanics and scope boundaries, not legal QA generalization. All three methods pass these twelve cases; this does not establish an advantage for hybrid retrieval. No hosted generation quality score is fabricated. Before public/legal use, add independently reviewed real-world questions, negative and adversarial cases, document-family holdouts, citation relevance/support grading, latency/cost measurements and pretrained-embedding comparisons.
