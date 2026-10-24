"""Resource-bounded parser boundary for uploads."""
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
from threading import BoundedSemaphore

from app.extraction import Extracted, ExtractionError

_slots = BoundedSemaphore(2)


class ParserBusy(Exception):
    pass


def parse_upload(data: bytes, filename: str, media_type: str | None) -> Extracted:
    if not _slots.acquire(blocking=False):
        raise ParserBusy
    try:
        try:
            process = subprocess.run(
                [sys.executable, '-m', 'app.extraction_worker', filename, media_type or ''],
                input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                cwd=Path(__file__).resolve().parents[1], timeout=15, check=False,
            )
        except subprocess.TimeoutExpired:
            raise ExtractionError('Document parsing exceeded 15 seconds; simplify the document or split it.') from None
        if process.returncode not in (0, 2):
            raise ExtractionError('Document parsing exceeded resource limits or failed; no data was stored.')
        result = json.loads(process.stdout)
        if process.returncode == 2:
            raise ExtractionError(result['error'])
        for key in ['effective_date', 'expiration_date']:
            if result[key]:
                result[key] = date.fromisoformat(result[key])
        return Extracted(**result)
    finally:
        _slots.release()
