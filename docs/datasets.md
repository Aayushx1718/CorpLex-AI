# Dataset and evaluation plan

No external corpus has been downloaded and no model has been trained. Confirm the exact release license and usage restrictions before downloading, redistributing or training. Public availability alone is not permission.

| Candidate | Useful signal | Limitation |
| --- | --- | --- |
| [CUAD](https://www.atticusprojectai.org/cuad) | Expert-annotated commercial contract spans across 41 clause categories; clause extraction/retrieval benchmark | Clause presence is not a legal risk label; acquisition contracts and annotation scope do not represent every NDA or employment agreement |
| [ContractNLI](https://stanfordnlp.github.io/contract-nli/) | Document-level entailment and evidence spans in NDAs | Narrow domain; entailment is not risk severity or financial loss |
| [LEDGAR / LexGLUE](https://github.com/coastalcph/lex-glue) | Provision-type classification and a reproducible legal NLP baseline | Label taxonomy does not encode company-specific risk; verify underlying source and benchmark licensing separately |
| [SEC EDGAR](https://www.sec.gov/edgar/search/) exhibits | Real commercial language for permitted evaluation and retrieval | Public filings may contain personal data; no risk ground truth, substantial duplicates, access/fair-use policy and rights review required |
| Original samples in this repository | Deterministic fixtures for extraction and financial calculations | Four tiny synthetic examples cannot support accuracy or generalization claims |

## Annotation and evaluation gates

1. Define a versioned rubric for a limited clause family (e.g. termination or liability), a business context, label definitions and an `uncertain` option. Have two qualified reviewers annotate a pilot, adjudicate disagreements and measure agreement. Record consent/rights, provenance and label rationale.
2. Split by originating agreement/company and near-duplicate cluster before fitting TF-IDF or feature selection. Keep test contracts sealed; prevent clause/version leakage across train and test. Track class imbalance and distribution shift.
3. Compare TF-IDF logistic regression to Random Forest and XGBoost using identical grouped splits and a documented search budget. Report per-class precision, recall, F1, macro F1, confusion matrix and support; use held-out probability calibration with Brier score/reliability plots where probabilities are meaningful. SHAP explains model behavior, not legal correctness.
4. Report sample sizes, confidence intervals and limitations. If enough independently labeled contracts cannot be obtained, deliver clause-type classification and transparent rule flags, explicitly withholding a validated risk classifier. Do not manufacture labels from heuristics and call the resulting validation independent.
5. RAG: curate answerable and unanswerable questions with gold source spans on held-out contracts. Measure recall@k, ranking quality, citation exactness/support, answer faithfulness and abstention. Compare lexical, dense and hybrid retrieval; record latency and model/prompt/index versions. Embedding similarity is not confidence or legal validity.

Data analytics validation uses independently computed expected obligations on synthetic fixtures; scenario tests compare formulas and currency handling, not invented realized losses.
