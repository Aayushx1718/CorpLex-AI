"""Bounded deterministic extraction. Offsets index canonical Unicode text, not bytes."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import PurePosixPath
import re
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.table import Table
from pypdf import PdfReader

EXTRACTOR_VERSION = "rules-0.2.0"
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 1_000_000
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class ExtractionError(ValueError):
    pass


@dataclass
class Extracted:
    text: str
    units: list[dict]
    metadata: dict
    warnings: list[str]
    clauses: list[dict]
    entities: list[dict]
    effective_date: date | None
    expiration_date: date | None


def validate_zip(data: bytes) -> None:
    try:
        with ZipFile(BytesIO(data)) as archive:
            members = archive.infolist()
            names = [m.filename for m in members]
            if len(members) > 1000 or len(names) != len(set(names)):
                raise ExtractionError("DOCX contains too many or duplicate ZIP entries.")
            if '[Content_Types].xml' not in names or 'word/document.xml' not in names:
                raise ExtractionError("File is not a supported DOCX document.")
            if sum(m.file_size for m in members) > 30 * 1024 * 1024:
                raise ExtractionError("Expanded DOCX exceeds 30 MiB.")
            for m in members:
                path = PurePosixPath(m.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in m.filename:
                    raise ExtractionError("DOCX contains unsafe entry paths.")
                if m.flag_bits & 1 or m.file_size > max(m.compress_size, 1) * 200:
                    raise ExtractionError("Encrypted or excessively compressed DOCX is unsupported.")
                if 'vbaproject' in m.filename.lower():
                    raise ExtractionError("Macro-enabled documents are unsupported.")
    except BadZipFile as exc:
        raise ExtractionError("Malformed DOCX ZIP archive.") from exc


def extract(data: bytes, filename: str, media_type: str | None) -> Extracted:
    if not data or len(data) > MAX_FILE_BYTES:
        raise ExtractionError("File must contain between 1 byte and 10 MiB.")
    suffix = PurePosixPath(filename.lower()).suffix
    expected = {'.pdf': PDF_MIME, '.docx': DOCX_MIME}.get(suffix)
    if expected is None:
        raise ExtractionError("Only PDF and DOCX files are supported.")
    if media_type not in (None, '', 'application/octet-stream', expected):
        raise ExtractionError("Content type does not match the file extension.")
    units, parts, metadata, warnings = [], [], {}, []
    position = 0

    def append(raw: str, kind: str, number: int):
        nonlocal position
        # A stable text representation; source offsets refer to this exact stored value.
        value = raw.replace('\r\n', '\n').replace('\r', '\n').strip()
        if '\x00' in value:
            raise ExtractionError("Document contains unsupported null characters.")
        if position + bool(parts) + len(value) > MAX_TEXT_CHARS:
            raise ExtractionError("Extracted text exceeds one million characters.")
        if len(units) >= 10_000:
            raise ExtractionError('Document exceeds 10,000 source blocks.')
        if parts:
            position += 1
        units.append({'kind': kind, 'number': number, 'char_start': position, 'char_end': position + len(value)})
        parts.append(value)
        position += len(value)

    try:
        if suffix == '.pdf':
            if not data.startswith(b'%PDF-'):
                raise ExtractionError("File signature is not PDF.")
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ExtractionError("Encrypted PDFs are unsupported; provide an unlocked copy.")
            if len(reader.pages) > 100:
                raise ExtractionError("PDF exceeds the 100-page limit.")
            for number, page in enumerate(reader.pages, 1):
                value = page.extract_text() or ''
                append(value, 'page', number)
                if not value.strip():
                    warnings.append(f'Page {number} has no extractable text; OCR may be required.')
            metadata['page_count'] = len(reader.pages)
            if reader.metadata:
                metadata['title'] = str(reader.metadata.get('/Title', ''))[:500]
                metadata['author'] = str(reader.metadata.get('/Author', ''))[:500]
        else:
            if not data.startswith(b'PK'):
                raise ExtractionError("File signature is not DOCX.")
            validate_zip(data)
            document = Document(BytesIO(data))
            for number, block in enumerate(document.iter_inner_content(), 1):
                if isinstance(block, Table):
                    value = '\n'.join('\t'.join(cell.text for cell in row.cells) for row in block.rows)
                    append(value, 'table', number)
                else:
                    append(block.text, 'paragraph', number)
            metadata = {'title': document.core_properties.title[:500], 'author': document.core_properties.author[:500]}
            warnings.append('DOCX anchors identify body paragraphs/tables, not rendered pages; headers, footers, text boxes and images are not extracted.')
    except ExtractionError:
        raise
    except Exception as exc:
        # Parser exception details can contain document content; do not return them.
        raise ExtractionError("Document could not be parsed as a supported PDF or DOCX.") from exc
    text = '\n'.join(parts)
    if not text.strip():
        raise ExtractionError("No extractable text found. Scanned/image-only documents require OCR.")
    clauses = split_clauses(text, units)
    if len(clauses) > 10_000:
        raise ExtractionError('Document exceeds 10,000 clause candidates.')
    entities, effective, expiration = extract_entities(text)
    warnings.append('Rule-based extraction is incomplete and requires human review; validated means structurally valid, not legally verified.')
    if not any(e['kind'] == 'party' for e in entities):
        warnings.append('No supported Parties: header found; parties require manual review.')
    if not re.search(r'(?m)^\d+[.)]\s+', text):
        warnings.append('No numbered clause headings found; source blocks are used as clause candidates.')
    return Extracted(text, units, metadata, warnings, clauses, entities, effective, expiration)


def split_clauses(text: str, units: list[dict]) -> list[dict]:
    starts = [m.start() for m in re.finditer(r'(?m)^\d+[.)]\s+', text)]
    # Keep the preamble: no extracted text is silently discarded.
    if not starts:
        starts = [u['char_start'] for u in units if u['char_end'] > u['char_start']]
    if not starts or starts[0] != 0:
        starts.insert(0, 0)
    clauses = []
    for start, end in zip(starts, starts[1:] + [len(text)]):
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start == end:
            continue
        value = text[start:end]
        unit = next((u for u in units if u['char_start'] <= start < u['char_end']), None)
        heading = re.sub(r'^\d+[.)]\s+', '', value.split('\n')[0]).split('. ')[0][:200]
        clauses.append({'ordinal': len(clauses) + 1, 'heading': heading, 'text_content': value,
                        'char_start': start, 'char_end': end,
                        'page_number': unit['number'] if unit and unit['kind'] == 'page' else None})
    return clauses


def extract_entities(text: str) -> tuple[list[dict], date | None, date | None]:
    entities = []

    def entity(kind, start, end, normalized, currency=None):
        if len(entities) >= 10_000:
            raise ExtractionError('Document exceeds 10,000 entity candidates.')
        entities.append({'kind': kind, 'raw_text': text[start:end], 'normalized_value': normalized,
                         'currency': currency, 'char_start': start, 'char_end': end})

    # Deliberately conservative formats, with exact character evidence.
    for match in re.finditer(r'\b(USD|EUR|GBP|INR|CAD|AUD|JPY|CHF)\s+((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,4})?)(?!\d|,\d|\.\d)', text):
        amount = Decimal(match[2].replace(',', ''))
        if amount >= Decimal('10000000000000000'):
            raise ExtractionError('Monetary value exceeds the supported numeric range.')
        entity('money', match.start(), match.end(), str(amount), match[1])
    for match in re.finditer(r'\b\d{4}-\d{2}-\d{2}\b', text):
        try:
            parsed = date.fromisoformat(match[0])
        except ValueError as exc:
            raise ExtractionError('Invalid ISO date in document; correct the source before ingestion.') from exc
        entity('date', match.start(), match.end(), parsed.isoformat())
    header = re.search(r'(?im)^Parties:\s*(.+?)(?:\n|$)', text)
    if header:
        for match in re.finditer(r'(?:^|\s+and\s+)(.*?)(?=\s+and\s+|$)', header[1].rstrip('.')):
            raw = match[1]
            start = header.start(1) + match.start(1) + len(raw) - len(raw.lstrip())
            end = header.start(1) + match.end(1)
            # Named party text including any explicit role, no company identity inference.
            name = text[start:end].strip()
            if name:
                entity('party', start, end, name)
    def labelled(label):
        match = re.search(rf'(?i)\b{label} date:\s*(\d{{4}}-\d{{2}}-\d{{2}})\b', text)
        return date.fromisoformat(match[1]) if match else None
    effective, expiration = labelled('effective'), labelled('expiration')
    if effective and expiration and expiration < effective:
        raise ExtractionError('Expiration date precedes effective date.')
    return entities, effective, expiration


def obligation_candidates(clause: dict, entities: list[dict]) -> list[dict]:
    value = clause['text_content']
    # Skip unnumbered preambles to avoid interpreting metadata as obligations.
    if not re.match(r'^\d+[.)]\s+', value):
        return []
    lower = value.lower()
    kind = next((kind for kind, pattern in [
        ('termination', r'\bterminat'), ('penalty', r'\bpenalt|\bcredit|\bdelay'),
        ('renewal', r'\brenew'), ('payment', r'\bpay\b|\bfees\b|\bcompensation\b'),
        ('notice', r'\bnotice\b'),
    ] if re.search(pattern, lower)), None)
    if not kind:
        return []
    money = [e for e in entities if e['kind'] == 'money' and clause['char_start'] <= e['char_start'] < clause['char_end']]
    # Multiple values (e.g. a daily rate and cap) cannot safely become one obligation amount.
    single = money[0] if len(money) == 1 else None
    return [{'kind': kind, 'description': value, 'amount': single['normalized_value'] if single else None,
             'currency': single['currency'] if single else None,
             'recurrence': 'monthly' if re.search(r'\bper month\b|\bmonthly\b', lower) else None}]
