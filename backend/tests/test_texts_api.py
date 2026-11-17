import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.database import add_missing_columns, get_db
from app.dependencies import get_llm_client
from app.main import app
from app.models import GeneratedText
from tests.helpers import fake_llm, fake_response

PROFILE = {
    "summary": None,
    "experiences": [
        {"title": "Dev Python", "company": "Ayoa", "period": "2023 - 2024",
         "activities": ["Desenvolvi APIs REST com FastAPI"]},
    ],
    "skills": [{"category": "Linguagens", "items": ["Python"]}],
    "projects": [], "education": [], "certifications": [], "languages": [],
}
TRACK = {
    "company": "Acme", "title": "Dev Backend", "seniority": "Júnior", "work_mode": None, "location": None,
    "required_requirements": ["Python", "Docker"], "preferred_requirements": [],
    "technologies": ["Python", "Docker"], "responsibilities": ["Manter APIs"], "benefits": [], "salary": None,
}
ANALYSIS = {
    "requirements": [
        {"requirement_id": "R1", "evidence": "Python", "explanation": "ok", "status": "meets"},
        {"requirement_id": "R2", "evidence": "Usei Docker", "explanation": "inventado", "status": "meets"},
    ],
    "strengths": [{"point": "APIs", "evidence": "Desenvolvi APIs REST com FastAPI"}],
    "gaps": ["Docker"], "resume_suggestions": [], "study_plan": [],
}
QUESTION = "Por que você quer trabalhar conosco?"


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


def setup_job(api, analyze: bool = True) -> int:
    assert api.put("/profile", json={"data": PROFILE, "raw_text": "cv"}).status_code == 200
    use_llm(fake_response(json.dumps({"tracks": [TRACK]})))
    job_id = api.post("/jobs", json={"text": "vaga"}).json()["id"]
    if analyze:
        use_llm(fake_response(json.dumps(ANALYSIS)))
        assert api.post(f"/jobs/{job_id}/analysis").status_code == 201
    return job_id


def draft(text: str) -> object:
    return fake_response(json.dumps({"text": text}))


def claim_list(*items) -> object:
    return fake_response(json.dumps({"claims": [{"claim": c, "evidence": e} for c, e in items]}))


def test_answer_is_generated_verified_and_saved(api, db) -> None:
    job_id = setup_job(api)
    text = ("Trabalho com Python e desenvolvi APIs REST com FastAPI na Ayoa. "
            "Tenho experiência com Docker. [PREENCHER: por que a Acme]")
    llm = use_llm(draft(text), claim_list(
        ("Trabalho com Python", "Python"),
        ("desenvolvi APIs REST com FastAPI na Ayoa", "Desenvolvi APIs REST com FastAPI"),
        ("Tenho experiência com Docker", None),
    ))

    response = api.post(f"/jobs/{job_id}/texts", json={"type": "answer", "question": QUESTION, "format": "audio_script"})

    assert response.status_code == 201
    body = response.json()
    assert body["text"] == text
    assert body["format"] == "audio_script"
    assert body["question"] == QUESTION
    assert body["placeholders"] == ["por que a Acme"]
    assert body["unsupported_claims"] == 1
    assert [c["supported"] for c in body["claims"]] == [True, True, False]
    assert "[[SEM SUPORTE: Tenho experiência com Docker]]" in body["highlighted_text"]
    assert body["profile_version"] == 1

    # generation prompt: profile, job, only the VERIFIED analysis, and the request
    generate, audit = (call.kwargs for call in llm.sdk.messages.create.call_args_list)
    content = generate["messages"][0]["content"]
    assert "Desenvolvi APIs REST com FastAPI" in content
    assert "Cargo: Dev Backend" in content
    assert '(obrigatório) Python: atende (evidência no perfil: "Python")' in content
    assert "(obrigatório) Docker: não atende" in content
    assert "Usei Docker" not in content  # the invented evidence was rejected in the analysis
    assert f"Pergunta: {QUESTION}" in content
    assert "Formato: audio_script" in content
    assert "[PREENCHER:" in generate["system"]
    # audit prompt receives the generated text
    assert text in audit["messages"][0]["content"]

    saved = db.query(GeneratedText).one()
    assert saved.details["unsupported_claims"] == 1


def test_history_lists_texts_newest_first(api) -> None:
    job_id = setup_job(api)
    use_llm(draft("Resumo com Python."), claim_list(("Python", "Python")))
    first = api.post(f"/jobs/{job_id}/texts", json={"type": "summary"}).json()
    use_llm(draft("Olá, equipe Acme. [PREENCHER: seu nome]"), claim_list())
    second = api.post(f"/jobs/{job_id}/texts", json={"type": "cover_letter"}).json()

    history = api.get(f"/jobs/{job_id}/texts").json()

    assert [t["id"] for t in history] == [second["id"], first["id"]]
    assert history[1]["type"] == "summary"
    assert history[1]["format"] == "written"


def test_requires_analysis(api) -> None:
    job_id = setup_job(api, analyze=False)
    llm = use_llm()

    response = api.post(f"/jobs/{job_id}/texts", json={"type": "summary"})

    assert response.status_code == 409
    assert "Analise a vaga" in response.json()["detail"]
    llm.sdk.messages.create.assert_not_called()


@pytest.mark.parametrize("payload", [
    {"type": "answer"},  # question missing
    {"type": "answer", "question": "   "},
    {"type": "summary", "question": "pergunta sem sentido aqui"},
    {"type": "cover_letter", "format": "audio_script"},
    {"type": "poema"},
])
def test_invalid_requests_are_rejected(api, payload) -> None:
    job_id = setup_job(api)
    llm = use_llm()
    assert api.post(f"/jobs/{job_id}/texts", json=payload).status_code == 422
    llm.sdk.messages.create.assert_not_called()


def test_invalid_audit_output_saves_nothing(api, db) -> None:
    job_id = setup_job(api)
    use_llm(draft("Uso Python."), fake_response('{"claims": [{"claim": '))

    assert api.post(f"/jobs/{job_id}/texts", json={"type": "summary"}).status_code == 502
    assert db.query(GeneratedText).count() == 0


def test_empty_text_returns_502(api) -> None:
    job_id = setup_job(api)
    use_llm(draft("   "))
    assert api.post(f"/jobs/{job_id}/texts", json={"type": "summary"}).status_code == 502


def test_unknown_job(api) -> None:
    use_llm()
    assert api.post("/jobs/999/texts", json={"type": "summary"}).status_code == 404
    assert api.get("/jobs/999/texts").status_code == 404


def test_add_missing_columns_upgrades_old_database() -> None:
    """A database created before Etapa 5 has generated_texts without format/details."""
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE generated_texts (id INTEGER PRIMARY KEY, job_id INTEGER, type VARCHAR(12), "
            "question TEXT, text TEXT, created_at DATETIME)"
        ))

    added = add_missing_columns(engine)

    assert sorted(added) == ["generated_texts.details", "generated_texts.format"]
    columns = {c["name"] for c in inspect(engine).get_columns("generated_texts")}
    assert {"format", "details"} <= columns
    assert add_missing_columns(engine) == []  # idempotent
