from types import SimpleNamespace
from unittest.mock import MagicMock

from app.config import Settings
from app.llm.client import LLMClient


def fake_response(text: str = "", stop_reason: str = "end_turn", input_tokens: int = 10, output_tokens: int = 5):
    return SimpleNamespace(
        model="test-model",
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        content=[SimpleNamespace(type="text", text=text)] if text else [],
    )


def make_settings(**overrides) -> Settings:
    base = {"anthropic_api_key": "k", "anthropic_model": "test-model", "anthropic_fallbacks": ""}
    return Settings(**{**base, **overrides})


def fake_llm(*responses) -> LLMClient:
    """LLMClient whose SDK returns the given responses in order."""
    sdk = MagicMock()
    sdk.messages.create.side_effect = list(responses)
    return LLMClient(settings=make_settings(), sdk=sdk)


def make_pdf(text: str) -> bytes:
    """Builds a minimal one-page PDF with selectable text (no external libraries)."""
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
