import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ml.data import CATEGORIES, digest
from app.ml.routes import build_ml_router
from app.ml.service import ModelUnavailable, activate, active_paths, model_status
from app.ml.training import read_dataset


@pytest.fixture
def synthetic_dataset(tmp_path):
    texts = ['assignment transfer consent assign delegate', 'audit examine records inspect books',
             'liability maximum damages aggregate cap', 'compete competitive business territory restriction',
             'termination convenience notice terminate without cause']
    rows = []
    for split in ['train', 'validation', 'calibration', 'test']:
        for label, value in zip(CATEGORIES, texts):
            for index in range(4):
                source = f'{split}-{label}-{index}'
                rows.append({'id': source, 'source_id': source, 'issuer_id': source, 'group': source,
                             'split': split, 'label': label, 'text': f'{value} {value} unique{split}{index}'})
    directory = tmp_path / 'dataset'
    directory.mkdir()
    content = ''.join(json.dumps(row) + '\n' for row in rows)
    (directory / 'clauses.jsonl').write_text(content)
    (directory / 'manifest.json').write_text(json.dumps({'task': 'clause_type', 'purpose': 'synthetic_test',
        'dataset': 'synthetic unit fixtures', 'categories': CATEGORIES, 'rows_sha256': digest(content.encode()),
        'license': {'name': 'Original test fixtures', 'verified': False}}))
    return directory


def test_public_training_gate_and_synthetic_activation_block(synthetic_dataset, tmp_path):
    with pytest.raises(ValueError, match='Synthetic'):
        read_dataset(synthetic_dataset)
    manifest = json.loads((synthetic_dataset / 'manifest.json').read_text())
    manifest['purpose'] = 'public_benchmark'
    (synthetic_dataset / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='License'):
        read_dataset(synthetic_dataset)
    run = tmp_path / 'runs/fixture'
    run.mkdir(parents=True)
    (run / 'report.json').write_text(json.dumps({'task': 'clause_type', 'deployable': False}))
    with pytest.raises(ModelUnavailable, match='synthetic'):
        activate(run, run.parent)


def test_dataset_tampering_and_cross_split_leakage(synthetic_dataset):
    data_path = synthetic_dataset / 'clauses.jsonl'
    content = data_path.read_text()
    data_path.write_text(content + ' ')
    with pytest.raises(ValueError, match='checksum'):
        read_dataset(synthetic_dataset, allow_synthetic=True)
    rows = [json.loads(line) for line in content.splitlines()]
    rows[-1]['issuer_id'] = rows[0]['issuer_id']
    modified = ''.join(json.dumps(row) + '\n' for row in rows)
    data_path.write_text(modified)
    manifest = json.loads((synthetic_dataset / 'manifest.json').read_text())
    manifest['rows_sha256'] = digest(modified.encode())
    (synthetic_dataset / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='leaks'):
        read_dataset(synthetic_dataset, allow_synthetic=True)


def test_status_and_inference_withhold_missing_model(tmp_path):
    dataset, artifacts = tmp_path / 'missing', tmp_path / 'artifacts'
    app = FastAPI()
    app.include_router(build_ml_router(SimpleNamespace(ml_dataset_dir=dataset, ml_artifacts_dir=artifacts)))
    with TestClient(app) as client:
        body = client.get('/api/ml/status').json()
        assert body['model_available'] is False and body['risk_model_available'] is False
        assert body['report'] is None
        response = client.post('/api/ml/classify', json={'text': 'A sufficiently long clause that must not produce an invented prediction.'})
        assert response.status_code == 503
        assert client.post('/api/ml/classify', json={'text': 'short'}).status_code == 422


def test_active_path_cannot_escape_local_artifacts(tmp_path):
    (tmp_path / 'active.json').write_text(json.dumps({'run': '../untrusted', 'report_sha256': 'x'}))
    with pytest.raises(ModelUnavailable):
        active_paths(tmp_path)


def test_metric_formulas_and_probability_calibration():
    np = pytest.importorskip('numpy')
    pytest.importorskip('sklearn')
    from app.ml.training import calibrate, metrics
    p = np.array([[.8, .2], [.7, .3]])
    result = metrics(np.array([0, 1]), p, ['a', 'b'])
    assert result['accuracy'] == .5
    assert result['multiclass_brier'] == pytest.approx(.53)
    assert result['log_loss'] == pytest.approx(-(np.log(.8) + np.log(.3)) / 2)
    assert result['confusion_matrix'] == [[1, 0], [1, 0]]
    calibrated = calibrate(p, 2)
    assert np.allclose(calibrated.sum(axis=1), 1)
    assert np.all(calibrated[:, 0] < p[:, 0])


def test_three_models_train_and_explain_but_fixture_is_never_deployable(synthetic_dataset, tmp_path):
    pytest.importorskip('sklearn')
    pytest.importorskip('shap')
    pytest.importorskip('xgboost')
    from app.ml.training import train
    run = tmp_path / 'artifacts' / 'fixture-run'
    result = train(synthetic_dataset, run, allow_synthetic=True, small_test=True)
    assert result['validation_scope'] == 'synthetic_test_only'
    assert result['deployable'] is False
    assert set(result['comparisons']) == {'logistic_regression', 'random_forest', 'xgboost'}
    for comparison in result['comparisons'].values():
        assert sum(row['support'] for row in comparison['test_calibrated']['per_class']) == 20
        assert len(comparison['test_calibrated']['confusion_matrix']) == 5
        assert 0.1 <= comparison['temperature'] <= 10
    assert result['shap_example']['method'] == 'SHAP'
    assert (run / 'split_manifest.json').exists()
    with pytest.raises(ModelUnavailable):
        activate(run, run.parent)


@pytest.mark.parametrize('name', ['random_forest', 'xgboost'])
def test_tree_shap_outputs_are_multiclass_and_additive(name):
    np = pytest.importorskip('numpy')
    pytest.importorskip('sklearn')
    pytest.importorskip('shap')
    pytest.importorskip('xgboost')
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier
    from xgboost import XGBClassifier
    from app.ml.training import explain
    texts = [f'{word} {word} document {i}' for word in ['assignment', 'audit', 'liability', 'compete', 'termination'] for i in range(4)]
    vectorizer = TfidfVectorizer()
    x = vectorizer.fit_transform(texts)
    y = np.repeat(np.arange(5), 4)
    model = RandomForestClassifier(n_estimators=5, random_state=42) if name == 'random_forest' else XGBClassifier(n_estimators=5, max_depth=2, objective='multi:softprob', num_class=5, n_jobs=2)
    model.fit(x, y)
    bundle = {'vectorizer': vectorizer, 'model': model, 'model_name': name, 'labels': CATEGORIES, 'background': x.toarray()}
    result = explain(bundle, texts[0])
    assert result['available'] is True and result['features']
    total = result['base_value'] + result['total_attribution']
    if name == 'random_forest':
        expected = float(model.predict_proba(vectorizer.transform([texts[0]]))[0].max())
    else:
        expected = float(model.predict(vectorizer.transform([texts[0]]), output_margin=True)[0].max())
    assert total == pytest.approx(expected, abs=1e-5)


def test_license_verifier_rejects_unrelated_evidence_without_changing_state(synthetic_dataset, monkeypatch):
    from io import BytesIO
    from app.ml.data import verify_license
    class Page(BytesIO):
        url = 'https://www.atticusprojectai.org/cuad'
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: Page(b'CUAD project without an applicable license statement'))
    with pytest.raises(ValueError, match='does not clearly'):
        verify_license(synthetic_dataset, Page.url)
    assert json.loads((synthetic_dataset / 'manifest.json').read_text())['license']['verified'] is False
    with pytest.raises(ValueError, match='official HTTPS'):
        verify_license(synthetic_dataset, 'https://untrusted.example/license')


def test_license_verification_records_evidence_hash(synthetic_dataset, monkeypatch):
    from io import BytesIO
    from app.ml.data import verify_license
    class Page(BytesIO):
        url = 'https://www.atticusprojectai.org/cuad'
    content = b'<p>CUAD synthetic test page. CC BY 4.0</p>'
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: Page(content))
    result = verify_license(synthetic_dataset, Page.url)
    assert result['verified'] is True
    assert result['evidence_sha256'] == digest(content)
    assert result['checked_at']
    # This is a mocked fixture page, never used as actual release evidence.


def test_archive_download_checksum_failure_does_not_write_file(tmp_path, monkeypatch):
    from io import BytesIO
    from app.ml.data import fetch_archive
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: BytesIO(b'wrong archive'))
    output = tmp_path / 'archive.zip'
    with pytest.raises(ValueError, match='checksum'):
        fetch_archive(output)
    assert not output.exists()
