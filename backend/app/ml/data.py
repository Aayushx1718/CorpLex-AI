"""CUAD positive-span classification adaptation, with source and leakage tracking."""
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime, timezone
import urllib.request

CATEGORIES = ['Anti-Assignment', 'Audit Rights', 'Cap On Liability', 'Non-Compete', 'Termination For Convenience']
SOURCE_COMMIT = '67faa0e6023b04fcaae6cc09497ab00e5d63a2a2'
SOURCE_URL = f'https://github.com/TheAtticusProject/cuad/tree/{SOURCE_COMMIT}'
ARCHIVE_SHA256 = 'f8161d18bea4e9c05e78fa6dda61c19c846fb8087ea969c172753bc2f45b999a'


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized(value: str) -> str:
    return ' '.join(re.findall(r'\w+', value.lower()))


def fetch_archive(destination: Path) -> str:
    url = f'https://raw.githubusercontent.com/TheAtticusProject/cuad/{SOURCE_COMMIT}/data.zip'
    with urllib.request.urlopen(url, timeout=60) as response:
        content = response.read(25 * 1024 * 1024 + 1)
    if digest(content) != ARCHIVE_SHA256:
        raise ValueError('Downloaded archive checksum differs from the pinned release.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return ARCHIVE_SHA256


def prepare(archive: Path, directory: Path) -> dict:
    from zipfile import ZipFile
    from collections import Counter, defaultdict
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    data = archive.read_bytes()
    if digest(data) != ARCHIVE_SHA256:
        raise ValueError('Archive checksum does not match the pinned official release.')
    with ZipFile(archive) as z:
        dataset = json.loads(z.read('CUADv1.json'))
    rows, source_spans = [], defaultdict(set)
    invalid, too_short = 0, 0
    for document in dataset['data']:
        source = document['title']
        issuer = source.split('_', 1)[0].casefold()
        for paragraph in document['paragraphs']:
            context = paragraph['context']
            for question in paragraph['qas']:
                label = question['id'].rsplit('__', 1)[-1]
                if label not in CATEGORIES:
                    continue
                for answer in question['answers']:
                    start, value = answer['answer_start'], answer['text']
                    if context[start:start + len(value)] != value:
                        invalid += 1
                        continue
                    if len(value.split()) < 12:
                        too_short += 1
                        continue
                    key = (source, start, start + len(value))
                    source_spans[key].add(label)
                    rows.append({'id': digest(f'{source}|{start}|{value}'.encode()), 'source_id': source,
                                 'issuer_id': issuer, 'source_start': start, 'source_end': start + len(value),
                                 'text': value, 'label': label})
    # A single-label adaptation cannot honestly retain a span labeled in two categories.
    ambiguous = {key for key, labels in source_spans.items() if len(labels) > 1}
    raw_count = len(rows)
    unique, conflicts = {}, 0
    text_labels = defaultdict(set)
    for row in rows:
        text_labels[normalized(row['text'])].add(row['label'])
    for row in rows:
        if (row['source_id'], row['source_start'], row['source_end']) in ambiguous or len(text_labels[normalized(row['text'])]) > 1:
            conflicts += 1
            continue
        unique[(row['source_id'], normalized(row['text']))] = row
    rows = sorted(unique.values(), key=lambda r: r['id'])
    if not rows:
        raise ValueError('No usable labeled spans found.')
    # Union related agreements, same issuers and duplicate/near-duplicate spans.
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)
    issuers, sources, exact = {}, {}, {}
    for index, row in enumerate(rows):
        for mapping, key in [(issuers, row['issuer_id']), (sources, row['source_id']), (exact, normalized(row['text']))]:
            if key in mapping:
                union(index, mapping[key])
            else:
                mapping[key] = index
    # This lexical criterion is a documented guard, not proof of semantic deduplication.
    matrix = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), max_features=12000, dtype=np.float32).fit_transform([normalized(r['text']) for r in rows])
    for start in range(0, len(rows), 128):
        similarity = cosine_similarity(matrix[start:start + 128], matrix)
        left, right = np.where(similarity >= 0.92)
        for a, b in zip(left, right):
            if start + a < b:
                union(start + a, int(b))
    groups = [f'cluster-{find(i)}' for i in range(len(rows))]
    # Fixed 60/15/10/15 train/validation/calibration/test; no seed search on test labels.
    indices = np.arange(len(rows))
    trainvalcal, test = next(GroupShuffleSplit(n_splits=1, test_size=.15, random_state=42).split(indices, groups=groups))
    trainval, cal_local = next(GroupShuffleSplit(n_splits=1, test_size=.10 / .85, random_state=43).split(trainvalcal, groups=np.array(groups)[trainvalcal]))
    calibration = trainvalcal[cal_local]
    remaining = trainvalcal[trainval]
    train_local, val_local = next(GroupShuffleSplit(n_splits=1, test_size=.15 / .75, random_state=44).split(remaining, groups=np.array(groups)[remaining]))
    splits = {'train': remaining[train_local], 'validation': remaining[val_local], 'calibration': calibration, 'test': test}
    for split, values in splits.items():
        for index in values:
            rows[int(index)]['split'] = split
            rows[int(index)]['group'] = groups[int(index)]
    directory.mkdir(parents=True, exist_ok=True)
    content = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows)
    (directory / 'clauses.jsonl').write_text(content)
    report = {'task': 'clause_type', 'dataset': 'CUADv1-five-category-adaptation', 'purpose': 'public_benchmark',
              'source_url': SOURCE_URL, 'source_commit': SOURCE_COMMIT, 'archive_sha256': digest(data),
              'rows_sha256': digest(content.encode()), 'categories': CATEGORIES,
              'citation': 'Hendrycks, Burns, Chen and Ball (2021). CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review. https://arxiv.org/abs/2103.06268',
              'license': {'name': 'CC-BY-4.0 (verification pending)', 'verified': False, 'evidence_url': None},
              'counts': {split: dict(Counter(r['label'] for r in rows if r['split'] == split)) for split in splits},
              'groups': dict(Counter(r['group'] for r in rows)),
              'exclusions': {'invalid_source_spans': invalid, 'short_spans': too_short, 'ambiguous_label_rows': conflicts,
                             'duplicate_within_document_rows': raw_count - conflicts - len(unique)},
              'near_duplicate_cosine_threshold': .92, 'split_seed': [42, 43, 44],
              'limitations': ['Positive gold spans only; not full-contract extraction or business-risk severity.',
                             'Custom grouped splits are not the official CUAD benchmark.',
                             'Issuer grouping is filename-derived and lexical clustering cannot prove absence of all leakage.']}
    (directory / 'manifest.json').write_text(json.dumps(report, indent=2))
    return report


def verify_license(directory: Path, url: str) -> dict:
    from urllib.parse import urlsplit
    allowed = {'www.atticusprojectai.org', 'huggingface.co'}
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.username or parsed.password:
        raise ValueError('License evidence must use an official HTTPS project or dataset-card URL.')
    with urllib.request.urlopen(url, timeout=20) as response:
        if urlsplit(response.url).hostname not in allowed:
            raise ValueError('Unexpected license-page redirect destination.')
        content = response.read(2_000_000).decode('utf-8')
    import html
    plain = re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', content)))
    if not re.search(r'CUAD|Contract Understanding Atticus', plain, re.I) or not re.search(r'cc[ -]?by[ -]?4[.]0|Creative Commons Attribution 4[.]0', plain, re.I):
        raise ValueError('Page does not clearly identify CUAD and a CC-BY-4.0 license; manual license review is required.')
    manifest_path = directory / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['license'] = {'name': 'CC-BY-4.0', 'verified': True, 'evidence_url': url,
                           'evidence_sha256': digest(content.encode()), 'checked_at': datetime.now(timezone.utc).isoformat()}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest['license']
