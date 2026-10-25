"""Only locally generated, explicitly activated, checksum-verified artifacts load."""
import importlib.metadata
import json
from pathlib import Path

from app.ml.data import digest


class ModelUnavailable(ValueError):
    pass


def model_status(dataset_dir: Path, artifacts_dir: Path, benchmark_path: Path | None = None) -> dict:
    installed = {}
    for name in ['scikit-learn', 'shap', 'xgboost-cpu', 'xgboost']:
        try:
            installed[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    dataset = None
    manifest = dataset_dir / 'manifest.json'
    if manifest.exists():
        try:
            raw = json.loads(manifest.read_text())
            dataset = {key: raw.get(key) for key in ['dataset', 'purpose', 'source_url', 'citation', 'license', 'counts', 'exclusions', 'limitations']}
        except (ValueError, OSError):
            pass
    result = {'task': 'clause_type', 'risk_model_available': False, 'model_available': False,
              'status': 'awaiting_dataset', 'installed_packages': installed, 'dataset': dataset,
              'report': None, 'message': 'No validated business-risk model. Prepare an appropriately licensed clause dataset first.'}
    if dataset:
        result['status'] = 'awaiting_training' if dataset.get('license', {}).get('verified') else 'license_verification_pending'
        result['message'] = 'Clause-type pipeline prepared; training is withheld until license verification succeeds.' if result['status'] == 'license_verification_pending' else 'Dataset prepared. Run the documented training and review before activating a model.'
    try:
        _, report = active_paths(artifacts_dir)
    except ModelUnavailable:
        if benchmark_path and benchmark_path.is_file():
            try:
                benchmark = json.loads(benchmark_path.read_text())
                if benchmark.get('task') == 'clause_type' and benchmark.get('validation_scope') == 'CUAD_positive_gold_spans_only' and benchmark.get('dataset', {}).get('license', {}).get('verified'):
                    result.update(status='published_benchmark_only', report=benchmark,
                                  dataset={key: benchmark['dataset'].get(key) for key in ['dataset','purpose','source_url','citation','license','counts','exclusions','limitations']},
                                  message='Recorded CUAD benchmark results are available. No local inference artifact is active; reproduce training and review/activate it to classify text.')
            except (OSError, ValueError, AttributeError):
                pass
        return result
    if 'scikit-learn' not in installed or 'shap' not in installed:
        result.update(status='ml_dependencies_missing', message='Install the optional ML dependency group before using the active artifact.')
        return result
    if result['dataset'] is None:
        result['dataset'] = {key: report['dataset'].get(key) for key in ['dataset', 'purpose', 'source_url', 'citation', 'license', 'counts', 'exclusions', 'limitations']}
    result.update(model_available=True, status='clause_model_available', report=report,
                  message='Closed-set clause-type model only. Uploaded clauses may be outside the benchmark distribution; every result requires review.')
    return result


def active_paths(root: Path) -> tuple[Path, dict]:
    try:
        active = json.loads((root / 'active.json').read_text())
        run = active['run']
        # Only one local child directory; request bodies can never select a path.
        if not isinstance(run, str) or not run or Path(run).name != run or run in ('.', '..') or '\\' in run:
            raise ValueError('Invalid run path.')
        base = root.resolve()
        directory = (root / run).resolve()
        if directory.parent != base:
            raise ValueError('Run escapes artifact root.')
        report_path, model_path = directory / 'report.json', directory / 'model.joblib'
        if report_path.is_symlink() or model_path.is_symlink():
            raise ValueError('Artifact links are unsupported.')
        report_content = report_path.read_bytes()
        report = json.loads(report_content)
        if not isinstance(report, dict) or digest(report_content) != active['report_sha256'] or report.get('task') != 'clause_type' or not report.get('deployable'):
            raise ValueError('Unreviewed or synthetic model.')
        if not report.get('dataset', {}).get('license', {}).get('verified'):
            raise ValueError('License not verified.')
        if digest(model_path.read_bytes()) != report['model_sha256']:
            raise ValueError('Artifact integrity check failed.')
        return model_path, report
    except (OSError, ValueError, KeyError, TypeError):
        raise ModelUnavailable('No reviewed, checksum-verified clause-type model is active.') from None


def activate(run_directory: Path, artifacts_root: Path) -> None:
    report_path = run_directory / 'report.json'
    report = json.loads(report_path.read_text())
    if run_directory.resolve().parent != artifacts_root.resolve() or not report.get('deployable') or report.get('task') != 'clause_type':
        raise ModelUnavailable('Only reviewed non-synthetic clause-type runs inside the artifact root can be activated.')
    if not report.get('dataset', {}).get('license', {}).get('verified') or digest((run_directory / 'model.joblib').read_bytes()) != report['model_sha256']:
        raise ModelUnavailable('License or artifact integrity check failed.')
    # This is a local CLI operation, never a public endpoint or automatic train side effect.
    (artifacts_root / 'active.json').write_text(json.dumps({'run': run_directory.name, 'report_sha256': digest(report_path.read_bytes())}, indent=2))


def classify(root: Path, value: str) -> dict:
    from app.ml.training import calibrate, explain
    import joblib
    import numpy as np
    path, report = active_paths(root)
    # joblib is pickle-based: only this trusted local, hash-verified training output may load.
    bundle = joblib.load(path)
    features = bundle['vectorizer'].transform([value])
    if not features.nnz:
        return {'label': None, 'abstained': True, 'manual_review_required': True,
                'reason': 'No vocabulary overlap. Cannot classify reliably.', 'probabilities': [], 'explanation': None}
    probabilities = calibrate(bundle['model'].predict_proba(features), bundle['temperature'])[0]
    best = int(np.argmax(probabilities))
    abstained = float(probabilities[best]) < .65
    return {'label': None if abstained else bundle['labels'][best], 'abstained': abstained,
            'manual_review_required': True, 'reason': 'Below heuristic review threshold.' if abstained else 'Clause type only; legal risk and out-of-domain validity are not established.',
            'probabilities': [{'label': label, 'probability': float(probabilities[i])} for i, label in enumerate(bundle['labels'])],
            'explanation': explain(bundle, value), 'model': report['selected_model'], 'task': 'clause_type'}
