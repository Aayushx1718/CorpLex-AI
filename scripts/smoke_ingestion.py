"""Exercise the running API through Vite using only a synthetic document.
Run from the repository root after starting both services. Creates a demo contract.
"""
from pathlib import Path
import httpx

root = Path(__file__).resolve().parents[1]
source = root / 'samples/generated/vendor.docx'
if not source.exists():
    raise SystemExit('Generate fixtures first: backend/.venv/bin/python scripts/generate_samples.py')
with httpx.Client(base_url='http://127.0.0.1:5173', timeout=30) as client:
    ids = []
    for _ in range(2):
        with source.open('rb') as file:
            response = client.post('/api/contracts', data={'contract_type': 'vendor', 'title': 'Synthetic vendor smoke demo'},
                                   files={'file': (source.name, file, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
        response.raise_for_status()
        body = response.json()
        document = body['document']
        assert len(document['clauses']) == 5
        assert [e['normalized_value'] for e in document['entities'] if e['kind'] == 'money'] == ['12000.00', '100.00', '1000.00']
        ids.append(document['id'])
    assert ids[0] == ids[1]
    assert response.status_code == 200 and body['duplicate'] is True
    saved = client.get('/api/documents/' + ids[0])
    saved.raise_for_status()
    for clause in saved.json()['clauses']:
        assert saved.json()['canonical_text'][clause['char_start']:clause['char_end']] == clause['text_content']
print('Live proxy upload, source evidence, persistence and deduplication passed.')
