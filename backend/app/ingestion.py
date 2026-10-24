"""Transactional PostgreSQL repository for the deterministic ingestion pipeline."""
import hashlib
import json
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text

from app.extraction import EXTRACTOR_VERSION, obligation_candidates
from app.parser import parse_upload


def document_detail(connection, document_id: UUID) -> dict:
    row = connection.execute(text('''
        SELECT v.id, v.contract_id, c.title, c.contract_type, v.version_number,
               v.original_filename, v.media_type, v.sha256, v.status,
               v.effective_date, v.expiration_date, v.created_at,
               s.canonical_text, s.source_units, s.metadata, s.warnings, s.extractor_version
        FROM document_versions v JOIN contracts c ON c.id = v.contract_id
        JOIN document_sources s ON s.document_version_id = v.id
        WHERE v.id = :id
    '''), {'id': document_id}).mappings().first()
    if not row:
        raise HTTPException(404, 'Ingested document not found.')
    result = dict(row)
    result['clauses'] = [dict(r) for r in connection.execute(text('''
        SELECT id, ordinal, heading, text_content, page_number, char_start, char_end
        FROM clauses WHERE document_version_id = :id ORDER BY ordinal
    '''), {'id': document_id}).mappings()]
    result['entities'] = [dict(r) for r in connection.execute(text('''
        SELECT kind, raw_text, normalized_value, currency, char_start, char_end
        FROM document_entities WHERE document_version_id = :id ORDER BY char_start, kind
    '''), {'id': document_id}).mappings()]
    result['obligations'] = [dict(r) for r in connection.execute(text('''
        SELECT o.id, o.clause_id, o.kind, o.description, o.amount, o.currency,
               o.due_date, o.recurrence, o.review_status
        FROM obligations o JOIN clauses c ON c.id = o.clause_id
        WHERE c.document_version_id = :id ORDER BY c.ordinal, o.id
    '''), {'id': document_id}).mappings()]
    for obligation in result['obligations']:
        if obligation['amount'] is not None:
            obligation['amount'] = str(obligation['amount'])
    return result


def ingest(engine, data: bytes, filename: str, media_type: str | None,
           contract_type: str, title: str | None, contract_id: UUID | None) -> tuple[dict, bool]:
    extracted = parse_upload(data, filename, media_type)
    sha = hashlib.sha256(data).hexdigest()
    with engine.begin() as connection:
        # Serialize byte-identical concurrent requests; the unique hash remains a DB backstop.
        connection.execute(text('SELECT pg_advisory_xact_lock(:key)'),
                           {'key': int(sha[:15], 16)})
        existing = connection.execute(text('''
            SELECT v.id, v.contract_id, c.contract_type FROM document_versions v
            JOIN contracts c ON c.id = v.contract_id WHERE v.sha256 = :sha
        '''), {'sha': sha}).mappings().first()
        if existing:
            if (contract_id and existing['contract_id'] != contract_id) or existing['contract_type'] != contract_type:
                raise HTTPException(409, 'Identical content already belongs to a different contract or type.')
            return document_detail(connection, existing['id']), True
        if contract_id:
            contract = connection.execute(text('SELECT id, contract_type FROM contracts WHERE id = :id FOR UPDATE'),
                                          {'id': contract_id}).mappings().first()
            if not contract:
                raise HTTPException(404, 'Contract to version was not found.')
            if contract['contract_type'] != contract_type:
                raise HTTPException(409, 'Contract type must match the existing contract.')
            version = connection.execute(text('SELECT COALESCE(MAX(version_number), 0) + 1 FROM document_versions WHERE contract_id = :id'),
                                         {'id': contract_id}).scalar_one()
        else:
            contract_id, version = uuid4(), 1
            connection.execute(text('INSERT INTO contracts(id, title, contract_type) VALUES (:id, :title, :type)'),
                               {'id': contract_id, 'title': title or filename, 'type': contract_type})
        document_id = uuid4()
        detected_mime = 'application/pdf' if filename.lower().endswith('.pdf') else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        connection.execute(text('''
            INSERT INTO document_versions(id, contract_id, version_number, original_filename,
            storage_key, media_type, sha256, status, effective_date, expiration_date)
            VALUES (:id, :contract, :version, :filename, :storage, :mime, :sha, 'validated', :effective, :expiration)
        '''), {'id': document_id, 'contract': contract_id, 'version': version, 'filename': filename,
              'storage': f'db:{document_id}', 'mime': detected_mime, 'sha': sha,
              'effective': extracted.effective_date, 'expiration': extracted.expiration_date})
        connection.execute(text('''
            INSERT INTO document_sources(document_version_id, original_content, canonical_text,
            source_units, metadata, warnings, extractor_version)
            VALUES (:id, :data, :source, CAST(:units AS jsonb), CAST(:metadata AS jsonb), CAST(:warnings AS jsonb), :extractor)
        '''), {'id': document_id, 'data': data, 'source': extracted.text,
              'units': json.dumps(extracted.units), 'metadata': json.dumps(extracted.metadata),
              'warnings': json.dumps(extracted.warnings), 'extractor': EXTRACTOR_VERSION})
        for entity in extracted.entities:
            connection.execute(text('''
                INSERT INTO document_entities(document_version_id, kind, raw_text, normalized_value, currency, char_start, char_end)
                VALUES (:document, :kind, :raw_text, :normalized_value, :currency, :char_start, :char_end)
            '''), {'document': document_id, **entity})
            if entity['kind'] == 'party':
                # Do not merge entities across contracts by unverified name similarity.
                party_id = uuid4()
                connection.execute(text('INSERT INTO parties(id, legal_name) VALUES (:id, :name)'),
                                   {'id': party_id, 'name': entity['normalized_value']})
                connection.execute(text("INSERT INTO contract_parties(document_version_id, party_id, role) VALUES (:document, :party, 'unspecified')"),
                                   {'document': document_id, 'party': party_id})
        for clause in extracted.clauses:
            clause_id = uuid4()
            connection.execute(text('''
                INSERT INTO clauses(id, document_version_id, ordinal, heading, text_content, page_number, char_start, char_end, extractor_version)
                VALUES (:id, :document, :ordinal, :heading, :text_content, :page_number, :char_start, :char_end, :extractor)
            '''), {'id': clause_id, 'document': document_id, 'extractor': EXTRACTOR_VERSION, **clause})
            for obligation in obligation_candidates(clause, extracted.entities):
                connection.execute(text('''
                    INSERT INTO obligations(clause_id, kind, description, amount, currency, recurrence)
                    VALUES (:clause, :kind, :description, :amount, :currency, :recurrence)
                '''), {'clause': clause_id, **obligation})
        connection.execute(text('''
            INSERT INTO audit_events(actor_id, action, entity_type, entity_id, details)
            VALUES ('local-development', 'document.ingested', 'document_version', :id, CAST(:details AS jsonb))
        '''), {'id': document_id, 'details': json.dumps({'extractor_version': EXTRACTOR_VERSION, 'sha256': sha})})
        return document_detail(connection, document_id), False
