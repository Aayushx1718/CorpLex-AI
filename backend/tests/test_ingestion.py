"""Real PostgreSQL tests in a disposable schema, never in the application's tables.
Run with TEST_DATABASE_URL set to a PostgreSQL SQLAlchemy URL.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path

from app.routes import build_router
from app.uploads import UploadLimitMiddleware
from app.extraction import DOCX_MIME, MAX_FILE_BYTES
from generate_samples import as_docx


@pytest.fixture
def db_engine():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL is required for PostgreSQL integration tests')
    schema = 'test_' + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA {schema}')
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        raw = engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                for name in ['001_initial.sql', '002_ingestion.sql']:
                    cursor.execute((Path(__file__).resolve().parents[2] / 'db' / name).read_text())
        finally:
            raw.close()
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA {schema} CASCADE')
        admin.dispose()


@pytest.fixture
def client(db_engine):
    app = FastAPI()
    app.add_middleware(UploadLimitMiddleware)
    app.include_router(build_router(db_engine))
    with TestClient(app) as client:
        yield client


def upload(client, data, **fields):
    return client.post('/api/contracts', files={'file': ('vendor.docx', data, DOCX_MIME)},
                       data={'contract_type': 'vendor', **fields})


def test_round_trip_dedup_and_versioning(client, docx_bytes, vendor_text, db_engine):
    response = upload(client, docx_bytes, title='Vendor agreement')
    assert response.status_code == 201, response.text
    body = response.json()
    assert body['duplicate'] is False
    document = body['document']
    assert len(document['clauses']) == 5
    assert len(document['entities']) == 7  # two dates, two parties, three money mentions
    assert all(o['review_status'] == 'pending' for o in document['obligations'])
    repeated = upload(client, docx_bytes)
    assert repeated.status_code == 200
    assert repeated.json()['duplicate'] is True
    assert repeated.json()['document']['id'] == document['id']
    assert client.get('/api/documents/' + document['id']).json() == document
    assert len(client.get('/api/contracts').json()['items']) == 1
    version = upload(client, as_docx(vendor_text.replace('12000.00', '15000.00')), contract_id=document['contract_id'])
    assert version.status_code == 201, version.text
    assert version.json()['document']['version_number'] == 2
    assert client.get('/api/contracts').json()['items'][0]['version_number'] == 2
    with db_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM contracts')).scalar_one() == 1
        assert conn.execute(text('SELECT count(*) FROM document_versions')).scalar_one() == 2
        assert conn.execute(text('SELECT original_content FROM document_sources WHERE document_version_id = :id'), {'id': document['id']}).scalar_one() == docx_bytes


def test_malformed_and_oversize_leave_no_rows(client, db_engine):
    assert upload(client, b'invalid').status_code == 422
    assert upload(client, b'x' * (MAX_FILE_BYTES + 1)).status_code == 413
    assert upload(client, b'x' * (MAX_FILE_BYTES + 100_000)).status_code == 413
    assert upload(client, as_docx('hello'), contract_type='unknown').status_code == 422
    assert client.get('/api/contracts?limit=101').status_code == 422
    assert client.get('/api/contracts').json()['items'] == []
    with db_engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM document_versions')).scalar_one() == 0


def test_database_failure_rolls_back_all_entities(client, db_engine, docx_bytes):
    def fail_on_clause(conn, cursor, statement, parameters, context, executemany):
        if 'INSERT INTO clauses' in statement:
            raise SQLAlchemyError('simulated persistence failure')
    event.listen(db_engine, 'before_cursor_execute', fail_on_clause)
    try:
        response = upload(client, docx_bytes)
    finally:
        event.remove(db_engine, 'before_cursor_execute', fail_on_clause)
    assert response.status_code == 503
    with db_engine.connect() as conn:
        for table in ['contracts', 'document_versions', 'document_sources', 'document_entities', 'parties', 'obligations', 'audit_events']:
            assert conn.execute(text(f'SELECT count(*) FROM {table}')).scalar_one() == 0
    assert upload(client, docx_bytes).status_code == 201


def test_unknown_contract_and_conflicting_duplicate(client, docx_bytes):
    assert upload(client, docx_bytes, contract_id=str(uuid4())).status_code == 404
    assert upload(client, docx_bytes).status_code == 201
    assert upload(client, docx_bytes, contract_type='nda').status_code == 409
    assert upload(client, docx_bytes, contract_id=str(uuid4())).status_code == 409
    assert client.get('/api/documents/' + str(uuid4())).status_code == 404


def test_concurrent_duplicate_upload_is_idempotent(client, docx_bytes):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: upload(client, docx_bytes), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 201]
    assert len({r.json()['document']['id'] for r in responses}) == 1
    assert len(client.get('/api/contracts').json()['items']) == 1


def test_chunked_upload_limit_without_content_length(client):
    def chunks():
        yield b'--test\r\nContent-Disposition: form-data; name="file"; filename="huge.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
        for _ in range(12):
            yield b'x' * 1024 * 1024
        yield b'\r\n--test--\r\n'
    response = client.post('/api/contracts', content=chunks(), headers={'Content-Type': 'multipart/form-data; boundary=test'})
    assert response.status_code == 413
