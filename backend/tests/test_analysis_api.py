import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_llm_client
from app.main import app
from app.models import Analysis
from tests.helpers import fake_llm, fake_response

PROFILE = {
    "summary": None,
    "experiences": [
        {"title": "Dev Python", "company": "Ayoa", "period": "2023 - 2024",
         "activities": ["Desenvolvi APIs REST com FastAPI"]},
    ],
    "skills": [{"category": "Linguagens", "items": ["Python"]}],
    "projects": [],
    "education": [],
    "certifications": [],
    "languages": [],
}


def track(**overrides) -> dict:
    base = {
        "company": "Acme", "title": "Dev Backend", "seniority": None, "work_mode": None, "location": None,
        "required_requirements": ["Python", "Docker"], "preferred_requirements": ["AWS"],
        "technologies": ["Python", "Docker", "AWS"], "responsibilities": [], "benefits": [], "salary": None,
    }
    return {**base, **overrides}


def model_analysis(requirements, **extra) -> str:
    body = {"requirements": requirements, "strengths": [], "gaps": [], "resume_suggestions": [], "study_plan": []}
    return json.dumps({**body, **extra})


def assessment(req_id, status, evidence=None):
    return {"requirement_id": req_id, "evidence": evidence, "explanation": "motivo", "status": status}


HONEST = model_analysis(
    [assessment("R1", "meets", "Python"), assessment("R2", "missing"), assessment("P1", "missing")],
    gaps=["Docker"], study_plan=["Fazer um projeto com Docker"],
)


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


def save_profile(api, data=PROFILE) -> None:
    assert api.put("/profile", json={"data": data, "raw_text": "cv"}).status_code == 200


def create_job(api, *tracks) -> int:
    use_llm(fake_response(json.dumps({"tracks": list(tracks or (track(),))})))
    return api.post("/jobs", json={"text": "vaga"}).json()["id"]


def test_analysis_sends_profile_and_numbered_requirements(api) -> None:
    save_profile(api)
    job_id = create_job(api)
    llm = use_llm(fake_response(HONEST))

    response = api.post(f"/jobs/{job_id}/analysis")

    assert response.status_code == 201
    body = response.json()
    assert body["score"] == 40  # R1 met (2) of R1+R2 (4) + P1 (1) -> 2/5
    assert body["profile_version"] == 1
    assert body["outdated"] is False
    assert body["track_title"] == "Dev Backend"
    assert body["gaps"] == ["Docker"]
    assert [r["requirement"] for r in body["requirements"]] == ["Python", "Docker", "AWS"]

    sent = llm.sdk.messages.create.call_args.kwargs
    content = sent["messages"][0]["content"]
    assert "Desenvolvi APIs REST com FastAPI" in content
    assert "R1 (obrigatório): Python" in content
    assert "P1 (desejável): AWS" in content
    assert f"<data_de_hoje>{date.today().isoformat()}</data_de_hoje>" in content
    assert "verbatim" in sent["system"]


def test_invented_evidence_is_caught(api, db) -> None:
    """The guide's key test: a model that invents evidence must be caught by code."""
    save_profile(api)
    job_id = create_job(api)
    lying = model_analysis([
        assessment("R1", "meets", "Python"),
        assessment("R2", "meets", "3 anos de experiência com Docker e Kubernetes"),
        assessment("P1", "meets", "Certificação AWS Solutions Architect"),
    ])
    use_llm(fake_response(lying))

    body = api.post(f"/jobs/{job_id}/analysis").json()

    docker = body["requirements"][1]
    assert docker["status"] == "missing"
    assert docker["model_status"] == "meets"
    assert docker["evidence_verified"] is False
    assert docker["note"] == "Evidência não encontrada no perfil."
    assert body["requirements"][2]["status"] == "missing"
    assert body["verification"]["evidence_rejected"] == 2
    # the model claimed 100%; the verified score is the same as the honest answer
    assert body["score"] == 40
    # and the verified version is what got saved
    saved = db.query(Analysis).one()
    assert saved.result["requirements"][1]["status"] == "missing"


def test_requires_saved_profile(api) -> None:
    job_id = create_job(api)
    llm = use_llm()

    response = api.post(f"/jobs/{job_id}/analysis")

    assert response.status_code == 409
    assert "perfil" in response.json()["detail"]
    llm.sdk.messages.create.assert_not_called()


def test_requires_track_choice(api) -> None:
    save_profile(api)
    job_id = create_job(api, track(title="AI Engineer"), track(title="AI Builder"))
    use_llm()

    assert api.post(f"/jobs/{job_id}/analysis").status_code == 409

    api.put(f"/jobs/{job_id}/track", json={"track": 1})
    use_llm(fake_response(HONEST))
    body = api.post(f"/jobs/{job_id}/analysis").json()
    assert body["track"] == 1
    assert body["track_title"] == "AI Builder"


def test_job_without_requirements_is_rejected(api) -> None:
    save_profile(api)
    job_id = create_job(api, track(required_requirements=[], preferred_requirements=[]))
    llm = use_llm()

    assert api.post(f"/jobs/{job_id}/analysis").status_code == 422
    llm.sdk.messages.create.assert_not_called()


def test_invalid_model_output_saves_nothing(api, db) -> None:
    save_profile(api)
    job_id = create_job(api)
    use_llm(fake_response('{"requirements": [{"requirement_id": "R1"'))

    assert api.post(f"/jobs/{job_id}/analysis").status_code == 502
    assert db.query(Analysis).count() == 0


def test_get_latest_analysis_and_outdated_after_profile_change(api) -> None:
    save_profile(api)
    job_id = create_job(api)
    assert api.get(f"/jobs/{job_id}/analysis").status_code == 404

    use_llm(fake_response(HONEST))
    api.post(f"/jobs/{job_id}/analysis")
    use_llm(fake_response(model_analysis([assessment("R1", "meets", "Python"), assessment("R2", "meets", "Python")])))
    second = api.post(f"/jobs/{job_id}/analysis").json()

    latest = api.get(f"/jobs/{job_id}/analysis").json()
    assert latest["id"] == second["id"]
    assert latest["outdated"] is False

    save_profile(api, {**PROFILE, "summary": "Dev backend"})  # profile v2
    latest = api.get(f"/jobs/{job_id}/analysis").json()
    assert latest["profile_version"] == 1
    assert latest["outdated"] is True


def test_analysis_of_unknown_job(api) -> None:
    use_llm()
    assert api.post("/jobs/999/analysis").status_code == 404
    assert api.get("/jobs/999/analysis").status_code == 404
