import json

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_llm_client
from app.main import app
from tests.helpers import fake_llm, fake_response, make_pdf

EXTRACTED = {
    "summary": "Desenvolvedor backend",
    "experiences": [{"title": "Dev", "company": "Ayoa", "period": "2023-2024", "activities": ["APIs em FastAPI"]}],
    "skills": [{"category": "Backend", "items": ["Python", "FastAPI"]}],
    "projects": [],
    "education": [],
    "certifications": [],
    "languages": [{"language": "Inglês", "level": None}],
}


@pytest.fixture
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def use_llm(*responses):
    llm = fake_llm(*responses)
    app.dependency_overrides[get_llm_client] = lambda: llm
    return llm


def upload(api, content: bytes, name: str = "cv.pdf"):
    return api.post("/profile/upload", files={"file": (name, content, "application/pdf")})


def test_upload_returns_draft_without_saving(api) -> None:
    llm = use_llm(fake_response(json.dumps(EXTRACTED)))

    response = upload(api, make_pdf("Desenvolvedor backend na Ayoa"))

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["experiences"][0]["company"] == "Ayoa"
    assert "Ayoa" in body["raw_text"]
    # resume text went to the model, inside the prompt
    sent = llm.sdk.messages.create.call_args.kwargs
    assert "Ayoa" in sent["messages"][0]["content"]
    assert "Do not deduce" in sent["system"]
    # nothing saved until the user confirms
    assert api.get("/profile").status_code == 404


def test_upload_invalid_model_output_returns_502(api) -> None:
    use_llm(fake_response('{"summary": "faltou o resto"'))

    response = upload(api, make_pdf("cv"))

    assert response.status_code == 502
    assert "formato" in response.json()["detail"]


def test_upload_model_refusal_returns_502(api) -> None:
    use_llm(fake_response("", stop_reason="refusal"))
    assert upload(api, make_pdf("cv")).status_code == 502


def test_upload_rejects_non_pdf(api) -> None:
    llm = use_llm()
    response = upload(api, b"nao sou pdf", name="cv.txt")
    assert response.status_code == 415
    llm.sdk.messages.create.assert_not_called()


def test_upload_rejects_pdf_without_text(api) -> None:
    from pypdf import PdfWriter
    import io

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    use_llm()

    assert upload(api, buffer.getvalue()).status_code == 422


def test_put_saves_and_versions_profile(api) -> None:
    first = api.put("/profile", json={"data": EXTRACTED, "raw_text": "cv"})
    assert first.status_code == 200
    assert first.json()["version"] == 1

    edited = {**EXTRACTED, "summary": "Desenvolvedor backend Python"}
    second = api.put("/profile", json={"data": edited, "raw_text": "cv"})
    assert second.json()["version"] == 2

    current = api.get("/profile").json()
    assert current["data"]["summary"] == "Desenvolvedor backend Python"
    assert current["version"] == 2


def test_put_rejects_invalid_profile(api) -> None:
    response = api.put("/profile", json={"data": {"experiences": [{"company": "sem cargo"}]}})
    assert response.status_code == 422
