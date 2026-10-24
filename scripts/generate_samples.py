"""Generate original synthetic PDF/DOCX fixtures; never downloads contract data."""
from pathlib import Path
from io import BytesIO
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]


def as_docx(text: str) -> bytes:
    document = Document()
    document.core_properties.title = 'CorpLex synthetic demonstration contract'
    document.core_properties.author = 'CorpLex AI'
    for line in text.splitlines():
        document.add_paragraph(line)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def as_pdf(text: str) -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, invariant=1)
    pdf.setTitle('CorpLex synthetic demonstration contract')
    pdf.setAuthor('CorpLex AI')
    y = 800
    # Wrap at word boundaries; preserve extractable line breaks.
    import textwrap
    for paragraph in text.splitlines():
        for line in textwrap.wrap(paragraph, width=95) or ['']:
            if y < 55:
                pdf.showPage()
                y = 800
            pdf.setFont('Helvetica', 10)
            pdf.drawString(40, y, line)
            y -= 15
    pdf.save()
    return output.getvalue()


if __name__ == '__main__':
    directory = ROOT / 'samples' / 'generated'
    directory.mkdir(exist_ok=True)
    for path in (ROOT / 'samples' / 'contracts').glob('*.txt'):
        content = path.read_text()
        (directory / f'{path.stem}.pdf').write_bytes(as_pdf(content))
        (directory / f'{path.stem}.docx').write_bytes(as_docx(content))
    print('Generated 8 synthetic fixtures in samples/generated/')
