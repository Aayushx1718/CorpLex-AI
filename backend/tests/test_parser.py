import subprocess
import pytest
from app.extraction import DOCX_MIME, ExtractionError
from app.parser import parse_upload


def test_parser_timeout_is_reported_and_slots_are_released(monkeypatch, docx_bytes):
    original = subprocess.run
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 15)
    monkeypatch.setattr(subprocess, 'run', timeout)
    # More attempts than available parser slots prove failures do not exhaust capacity.
    for _ in range(3):
        with pytest.raises(ExtractionError, match='15 seconds'):
            parse_upload(docx_bytes, 'vendor.docx', DOCX_MIME)
    monkeypatch.setattr(subprocess, 'run', original)
    assert parse_upload(docx_bytes, 'vendor.docx', DOCX_MIME).effective_date.isoformat() == '2026-03-01'
