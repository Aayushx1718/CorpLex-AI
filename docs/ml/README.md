# Phase 4 — gated clause-type experiments

## Current state

The official CUAD dataset card is now accessible and declares `license: cc-by-4.0`. Verification records the exact official URL, content hash and retrieval time. The pinned source was prepared, all three fixed-budget models were trained/evaluated, and the validation-selected Logistic Regression model was reviewed and activated locally. No business-risk model is claimed.

| Model | Validation macro F1 | Held-out test macro F1 | Test Brier, calibrated |
| --- | --- | --- | --- |
| Logistic Regression | 0.9606 | 0.9479 | 0.0600 |
| Random Forest | 0.9315 | 0.9027 | 0.0932 |
| XGBoost | 0.9268 | 0.9397 | 0.0796 |

These are results on 361 held-out **positive gold spans across five categories**, not official CUAD extraction scores, full-contract accuracy or legal-risk validation. Train/validation/calibration/test sizes are 1,454/378/209/361. The selected model's 100-resample group-bootstrap macro-F1 interval is approximately [0.9183, 0.9786]; the smallest test class has only 21 spans. Logistic Regression's Brier score improved from 0.1449 to 0.0600 after calibration; XGBoost's slightly worsened, so calibration is not universally beneficial. Full metrics, confusion matrices, support, reliability bins, parameters, hashes and versions are preserved in [experiment-results.json](experiment-results.json).

Synthetic fixtures still test the pipeline mechanically and cannot activate. Raw corpus text and pickle artifacts remain ignored by Git; the trained artifact is available in the current cloud filesystem. A clean clone must reproduce training/activation using the commands below.

## Task and corpus scope

Selected CUAD categories: Anti-Assignment, Audit Rights, Cap On Liability, Non-Compete and Termination For Convenience. Targets are original expert-annotated **clause categories**, not arbitrary low/medium/high risk labels. Training text is the positive gold answer span, not the whole agreement, question wording or derived annotation rationale. This adapts span extraction into single-label classification; it is not the official CUAD evaluation.

Each row retains its agreement title, issuer proxy, source character offsets, gold text and label. Source offsets must reproduce the annotation text exactly. Short spans (<12 words), conflicting labels for identical spans/text and repeated same-document spans are excluded and counted. The dataset and generated artifacts are ignored by Git; they are not redistributed in the repository.

The release's commonly published license is CC-BY-4.0, and the verified official metadata is retained in the experiment report. An evidence page must identify CUAD in its body or be the exact official CUAD dataset-card URL, and must declare that license. The verifier records URL, content checksum and UTC retrieval time. The pinned source and paper citation remain in every report. If the release has different or additional terms, review them and update the workflow separately; do not bypass the gate by editing `verified` manually.

## Reproduce preparation

From the repository root, install the optional CPU ML group:

```bash
UV_CACHE_DIR=/tmp/corplex-uv-cache uv sync --project backend --frozen --group ml
cd backend
.venv/bin/python -m app.ml.cli fetch-cuad --output ../data/external/cuad/data.zip
.venv/bin/python -m app.ml.cli prepare-cuad \
  --archive ../data/external/cuad/data.zip --output ../data/external/cuad
```

Source: `https://github.com/TheAtticusProject/cuad/tree/67faa0e6023b04fcaae6cc09497ab00e5d63a2a2`.
Archive SHA-256: `f8161d18bea4e9c05e78fa6dda61c19c846fb8087ea969c172753bc2f45b999a`.
A checksum mismatch fails; it is never replaced just to accept another artifact.

Related agreements are connected by source ID and a filename-derived issuer proxy. Normalized duplicates and char-3–5 TF-IDF cosine similarity >=0.92 also connect groups transitively. Clustering uses the full corpus only to establish split boundaries; its features are never reused by a classifier. GroupShuffleSplit uses fixed seeds 42/43/44 and nominal 60/15/10/15 train/validation/calibration/test proportions by group, not exact row quotas. No seed search uses test results. At least five rows per class per split are required before public training. These are minimum mechanical gates, not proof of adequate statistical power.

Issuer proxies and lexical clustering cannot establish absence of all company/semantic leakage. Reports retain this limitation, per-class counts and group membership. No accuracy claim extends beyond this selected positive-span distribution.

## Verify the release license

Network access to `huggingface.co` is now verified in the published environment. The project website still returned HTTP 403, but the official dataset card supplies the required license declaration. To reproduce verification, run from `backend/`:

```bash
.venv/bin/python -m app.ml.cli verify-license \
  --dataset ../data/external/cuad \
  --url https://huggingface.co/datasets/theatticusproject/cuad/raw/main/README.md
```

Alternatively use the official CUAD project page if it clearly states the applicable license. The verifier rejects ambiguous evidence rather than inventing approval. Network saving does not itself establish runtime access. Do not paste credentials into chat; these public pages should require none.

## Train, inspect, then activate

Only after license verification succeeds:

```bash
.venv/bin/python -m app.ml.cli train \
  --dataset ../data/external/cuad --output ../artifacts/ml/cuad-v1
```

The command refuses unverified data, checksum changes, cross-split source/issuer/cluster/exact-text leakage, missing labels and insufficient support. TF-IDF (unigrams/bigrams, max 6,000 features, min_df=2) is fit on training text only. Fixed-budget models:

- Logistic regression, balanced class weights, max 1,000 iterations.
- Random Forest, 200 trees, depth 24, balanced class weights.
- CPU XGBoost, 200 trees, depth 4, learning rate .08, balanced sample weights.

Parallelism is limited to two threads. No GPU, model download or hyperparameter search is required. Each model fits scalar temperature calibration on the independent calibration split. Model selection uses validation macro F1 only. Test metrics are calculated once for the frozen configurations; the selected model is never chosen by test F1. Reports include per-class precision/recall/F1/support, confusion matrices, accuracy, multiclass Brier score, log loss, ten-bin reliability data/ECE and group-bootstrap macro-F1 intervals when at least ten independent test groups exist. Calibration can worsen held-out metrics; both raw and calibrated results are retained.

The 0.65 probability threshold is a declared operational abstention heuristic. Its observed coverage/accuracy are reported, but it is not a validated legal-risk threshold. Unseen categories, complete clauses and domains such as employment contracts may be out of distribution; vocabulary overlap and probability do not solve OOD detection.

Inspect `report.json`, `split_manifest.json`, sample counts, confidence intervals and limitations. Every run has a new output directory; training does not overwrite an existing result or automatically activate it. A local explicit activation step is available after review:

```bash
.venv/bin/python -m app.ml.cli activate --run ../artifacts/ml/cuad-v1 --root ../artifacts/ml
```

Only non-synthetic reviewed clause-type artifacts with verified-license metadata and matching checksums can activate. `joblib` is pickle-based: never replace these files with downloaded or user-uploaded models. The service checks the pinned report/model hashes and restricts paths to one local run directory. This is integrity checking for trusted local artifacts, not a sandbox for untrusted pickle files. Do not use activation as a route to bypass license verification.

## SHAP and serving

LinearExplainer explains logistic-regression logits; TreeExplainer explains RF probabilities or XGBoost margins. The UI shows the strongest present TF-IDF terms and states the output unit. Calibration is nonlinear: those SHAP values do not sum to calibrated probability. Omitted/absent features may contribute; explanations describe model behavior, never legal correctness or risk.

`GET /api/ml/status` reports provenance, preparation counts and activation state without inventing scores. `POST /api/ml/classify` accepts `{"text":"..."}` only when a real reviewed artifact is active; otherwise it returns 503. Empty vocabulary or probability below .65 abstains. Every result requires human review. No prediction is automatically stored as an approved obligation or risk decision.

Default local paths are `data/external/cuad/` and `artifacts/ml/`, configurable with `ML_DATASET_DIR` and `ML_ARTIFACTS_DIR`. No API keys are required. Model artifacts must be regenerated/reviewed if dependencies or source data change.

## Business-risk work remains separate

A legal-risk rubric, expert-reviewed labels, annotation agreement, company context and adequate independent test contracts remain prerequisites for a business-risk model. Do not convert clause-type probabilities into risk scores, use heuristic labels as independent ground truth, or claim the four synthetic contracts establish generalization.

References: [CUAD paper](https://arxiv.org/abs/2103.06268), [XGBoost](https://arxiv.org/abs/1603.02754), [SHAP](https://arxiv.org/abs/1705.07874).
