import io

import pytest
from pypdf import PdfWriter

from app.pdf import PdfError, extract_pdf_text
from tests.helpers import make_pdf


def test_extracts_text() -> None:
    assert "Desenvolvedor Python" in extract_pdf_text(make_pdf("Desenvolvedor Python"))


def test_pdf_without_text_raises() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(PdfError, match="escaneada"):
        extract_pdf_text(buffer.getvalue())


def test_corrupted_pdf_raises() -> None:
    with pytest.raises(PdfError):
        extract_pdf_text(b"%PDF-1.4 lixo")
