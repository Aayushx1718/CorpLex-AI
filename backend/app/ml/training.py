"""Offline fixed-budget experiments. No synthetic or unlicensed model is activated."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import shutil
import platform

from app.ml.data import digest, normalized

SPLITS = ('train', 'validation', 'calibration', 'test')


def read_dataset(directory: Path, allow_synthetic: bool = False):
    manifest = json.loads((directory / 'manifest.json').read_text())
    content = (directory / 'clauses.jsonl').read_bytes()
    if digest(content) != manifest['rows_sha256']:
        raise ValueError('Dataset checksum mismatch; prepare and review the source again.')
    if manifest.get('purpose') not in ('public_benchmark', 'synthetic_test'):
        raise ValueError('Dataset purpose must be explicitly declared.')
    synthetic = manifest.get('purpose') == 'synthetic_test'
    if synthetic and not allow_synthetic:
        raise ValueError('Synthetic test data cannot be used for a public model.')
    if not synthetic and not manifest.get('license', {}).get('verified'):
        raise ValueError('License verification is pending. No model will be trained or activated.')
    if manifest.get('task') != 'clause_type':
        raise ValueError('This pipeline supports clause types, not legal-risk labels.')
    rows = [json.loads(line) for line in content.decode().splitlines() if line]
    if not rows:
        raise ValueError('Empty dataset.')
    labels = sorted(manifest['categories'])
    seen = defaultdict(set)
    counts = defaultdict(Counter)
    for row in rows:
        if row['split'] not in SPLITS or row['label'] not in labels or not row['text'].strip():
            raise ValueError('Invalid split, label or text.')
        for key in ['source_id', 'issuer_id', 'group']:
            seen[(key, row[key])].add(row['split'])
        seen[('text', normalized(row['text']))].add(row['split'])
        counts[row['split']][row['label']] += 1
    if any(len(splits) > 1 for splits in seen.values()):
        raise ValueError('Source, issuer, duplicate text or duplicate cluster leaks between splits.')
    minimum = 2 if synthetic else 5
    for split in SPLITS:
        if any(counts[split][label] < minimum for label in labels):
            raise ValueError(f'Insufficient independent labeled support in {split}; do not reseed based on test results.')
    return manifest, rows, labels


def calibrate(probabilities, temperature):
    import numpy as np
    from scipy.special import softmax
    return softmax(np.log(np.clip(probabilities, 1e-9, 1)) / temperature, axis=1)


def metrics(y, probabilities, labels):
    import numpy as np
    from sklearn.metrics import accuracy_score, confusion_matrix, log_loss, precision_recall_fscore_support
    predicted = probabilities.argmax(axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(y, predicted, labels=list(range(len(labels))), zero_division=0)
    confidence = probabilities.max(axis=1)
    reliability = []
    for low in np.linspace(0, .9, 10):
        mask = (confidence >= low) & (confidence < low + .1 if low < .9 else confidence <= 1)
        reliability.append({'lower': float(low), 'upper': float(low + .1), 'count': int(mask.sum()),
                            'confidence': float(confidence[mask].mean()) if mask.any() else None,
                            'accuracy': float((predicted[mask] == y[mask]).mean()) if mask.any() else None})
    accepted = confidence >= .65
    return {'accuracy': float(accuracy_score(y, predicted)), 'macro_f1': float(f1.mean()),
            'per_class': [{'label': label, 'precision': float(precision[i]), 'recall': float(recall[i]), 'f1': float(f1[i]), 'support': int(support[i])} for i, label in enumerate(labels)],
            'confusion_matrix': confusion_matrix(y, predicted, labels=list(range(len(labels)))).tolist(),
            'log_loss': float(log_loss(y, probabilities, labels=list(range(len(labels))))),
            'multiclass_brier': float(np.mean(np.sum((probabilities - np.eye(len(labels))[y]) ** 2, axis=1))),
            'expected_calibration_error': float(sum(b['count'] * abs(b['confidence'] - b['accuracy']) for b in reliability if b['count']) / len(y)),
            'reliability_bins': reliability, 'review_threshold': .65,
            'threshold_coverage': float(accepted.mean()),
            'threshold_accuracy': float((predicted[accepted] == y[accepted]).mean()) if accepted.any() else None}


def bootstrap_interval(y, probabilities, groups, label_count):
    import numpy as np
    from sklearn.metrics import f1_score
    unique = sorted(set(groups))
    if len(unique) < 10:
        return {'available': False, 'reason': 'Fewer than ten independent test groups.'}
    indices = {g: np.where(np.array(groups) == g)[0] for g in unique}
    rng = np.random.default_rng(73)
    scores = []
    for _ in range(100):
        sampled = np.concatenate([indices[g] for g in rng.choice(unique, size=len(unique), replace=True)])
        scores.append(f1_score(y[sampled], probabilities[sampled].argmax(axis=1), labels=list(range(label_count)), average='macro', zero_division=0))
    low, high = np.quantile(scores, [.025, .975])
    return {'available': True, 'unit': 'duplicate/issuer group', 'resamples': 100, 'macro_f1_95_percent': [float(low), float(high)]}


def explain(bundle, text: str, top_k: int = 10):
    import numpy as np
    import shap
    vectorizer, model = bundle['vectorizer'], bundle['model']
    features = vectorizer.transform([text])
    if not features.nnz:
        return {'available': False, 'reason': 'No vocabulary overlap.'}
    raw = model.predict_proba(features)
    target = int(raw.argmax(axis=1)[0])
    if bundle['model_name'] == 'logistic_regression':
        explainer = shap.LinearExplainer(model, bundle['background'])
        unit = 'uncalibrated class logit'
    else:
        explainer = shap.TreeExplainer(model)
        unit = 'uncalibrated class probability' if bundle['model_name'] == 'random_forest' else 'uncalibrated class margin'
    values = np.asarray(explainer.shap_values(features.toarray()))
    if values.ndim != 3 or values.shape[2] != len(bundle['labels']):
        raise ValueError('Unexpected multiclass SHAP output shape.')
    contributions = values[0, :, target]
    names = vectorizer.get_feature_names_out()
    present = features.indices
    strongest = sorted(present, key=lambda i: abs(contributions[i]), reverse=True)[:top_k]
    expected = np.asarray(explainer.expected_value).reshape(-1)
    return {'available': True, 'method': 'SHAP', 'label': bundle['labels'][target], 'output_unit': unit,
            'base_value': float(expected[target]), 'total_attribution': float(contributions.sum()),
            'features': [{'feature': str(names[i]), 'contribution': float(contributions[i])} for i in strongest],
            'note': 'Top present TF-IDF features only; omitted/absent features can also contribute. Explains the original model output, not calibrated probability, legal correctness or risk.'}


def train(directory: Path, output: Path, allow_synthetic: bool = False, small_test: bool = False):
    import importlib.metadata
    import joblib
    import numpy as np
    from scipy.optimize import minimize_scalar
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss
    from sklearn.utils.class_weight import compute_sample_weight
    from threadpoolctl import threadpool_limits
    from xgboost import XGBClassifier

    manifest, rows, labels = read_dataset(directory, allow_synthetic)
    if small_test and manifest['purpose'] != 'synthetic_test':
        raise ValueError('Small test configurations cannot be used for a public benchmark.')
    grouped = {split: [row for row in rows if row['split'] == split] for split in SPLITS}
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=6000, min_df=2, sublinear_tf=True, strip_accents='unicode')
    x = {'train': vectorizer.fit_transform([r['text'] for r in grouped['train']])}
    x.update({split: vectorizer.transform([r['text'] for r in grouped[split]]) for split in SPLITS if split != 'train'})
    y = {split: np.array([labels.index(r['label']) for r in grouped[split]]) for split in SPLITS}
    models = {
        'logistic_regression': LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42),
        'random_forest': RandomForestClassifier(n_estimators=12 if small_test else 200, max_depth=24, class_weight='balanced', random_state=42, n_jobs=2),
        'xgboost': XGBClassifier(n_estimators=8 if small_test else 200, max_depth=4, learning_rate=.08, subsample=.9, colsample_bytree=.8, objective='multi:softprob', num_class=len(labels), eval_metric='mlogloss', random_state=42, n_jobs=2, tree_method='hist'),
    }
    results, bundles = {}, {}
    with threadpool_limits(limits=2):
        for name, model in models.items():
            kwargs = {'sample_weight': compute_sample_weight('balanced', y['train'])} if name == 'xgboost' else {}
            model.fit(x['train'], y['train'], **kwargs)
            calibration = model.predict_proba(x['calibration'])
            fit = minimize_scalar(lambda t: log_loss(y['calibration'], calibrate(calibration, t), labels=list(range(len(labels)))), bounds=(.1, 10), method='bounded')
            if not fit.success:
                raise ValueError('Temperature fitting failed.')
            temperature = float(fit.x)
            validation = metrics(y['validation'], model.predict_proba(x['validation']), labels)
            raw_test = model.predict_proba(x['test'])
            calibrated_test = calibrate(raw_test, temperature)
            results[name] = {'parameters': model.get_params(), 'temperature': temperature,
                             'validation': validation, 'test_raw': metrics(y['test'], raw_test, labels),
                             'test_calibrated': metrics(y['test'], calibrated_test, labels),
                             'confidence_interval': bootstrap_interval(y['test'], calibrated_test, [r['group'] for r in grouped['test']], len(labels))}
            bundles[name] = {'vectorizer': vectorizer, 'model': model, 'model_name': name, 'temperature': temperature,
                             'labels': labels, 'background': x['train'][:50].toarray()}
        # Selection uses validation only, never test metrics.
        winner = max(models, key=lambda name: results[name]['validation']['macro_f1'])
        example = explain(bundles[winner], grouped['test'][0]['text'])
    synthetic = manifest['purpose'] == 'synthetic_test'
    xgboost_package = 'xgboost-cpu'
    try:
        importlib.metadata.version(xgboost_package)
    except importlib.metadata.PackageNotFoundError:
        xgboost_package = 'xgboost'
    report = {'task': 'clause_type', 'trained': True, 'deployable': not synthetic,
              'validation_scope': 'synthetic_test_only' if synthetic else 'CUAD_positive_gold_spans_only',
              'created_at': datetime.now(timezone.utc).isoformat(), 'dataset': manifest,
              'split_sizes': {split: len(grouped[split]) for split in SPLITS},
              'selection_rule': 'Highest validation macro F1; fixed configurations; ties retain model order.',
              'selected_model': winner, 'comparisons': results, 'shap_example': example,
              'versions': {name: importlib.metadata.version(name) for name in ['scikit-learn', 'shap', 'numpy', 'scipy', xgboost_package]},
              'python': platform.python_version(),
              'limitations': ['Clause type is not legal risk. No validated low/medium/high risk model.',
                             'Positive gold spans only; full uploaded clauses and unseen categories are out of distribution.',
                             'The 0.65 review threshold is an operational heuristic, not a legal confidence guarantee.',
                             'Temperature scaling and a small held-out test do not establish production calibration.']}
    if output.exists():
        raise ValueError('Output directory already exists; use a new versioned run directory.')
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.training-', dir=output.parent))
    try:
        artifact = staging / 'model.joblib'
        joblib.dump(bundles[winner], artifact)
        report['model_sha256'] = digest(artifact.read_bytes())
        (staging / 'report.json').write_text(json.dumps(report, indent=2, default=str))
        (staging / 'split_manifest.json').write_text(json.dumps([{k: r[k] for k in ['id', 'source_id', 'issuer_id', 'group', 'split', 'label']} for r in rows], indent=2))
        staging.rename(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return report
