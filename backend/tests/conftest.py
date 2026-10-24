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
