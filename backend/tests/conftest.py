from io import BytesIO
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from generate_samples import as_docx, as_pdf


@pytest.fixture
def vendor_text():
    return (Path(__file__).resolve().parents[2] / 'samples/contracts/vendor.txt').read_text()


@pytest.fixture
def docx_bytes(vendor_text):
    return as_docx(vendor_text)


@pytest.fixture
def pdf_bytes(vendor_text):
    return as_pdf(vendor_text)

import os
from uuid import uuid4
from sqlalchemy import create_engine


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
                for name in ['001_initial.sql', '002_ingestion.sql', '003_analytics.sql']:
                    cursor.execute((Path(__file__).resolve().parents[2] / 'db' / name).read_text())
        finally:
            raw.close()
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA {schema} CASCADE')
        admin.dispose()
