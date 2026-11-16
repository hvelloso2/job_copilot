import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfError(Exception):
    pass


def extract_pdf_text(content: bytes) -> str:
    """Extracts the text of every page. Raises PdfError if the file is invalid or has no text."""
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, OSError) as exc:
        raise PdfError("Não foi possível ler o PDF.") from exc

    text = "\n\n".join(p.strip() for p in pages if p.strip())
    if not text:
        raise PdfError("O PDF não tem texto selecionável (pode ser uma imagem escaneada).")
    return text
