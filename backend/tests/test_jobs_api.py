import json

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_llm_client
from app.main import app
from tests.helpers import fake_llm, fake_response

POSTING = "Acme contrata Dev Backend Pleno. Requisitos: Python e Django. Diferencial: AWS. Remoto."


def track(**overrides) -> dict:
    base = {
        "company": "Acme",
        "title": "Dev Backend",
        "seniority": "Pleno",
        "work_mode": "remote",
        "location": None,
        "required_requirements": ["Python", "Django"],
        "preferred_requirements": ["AWS"],
        "technologies": ["Python", "Django", "AWS"],
        "responsibilities": ["Manter APIs"],
        "benefits": [],
        "salary": None,
    }
    return {**base, **overrides}


def extraction(*tracks: dict) -> str:
    return json.dumps({"tracks": list(tracks)})


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


def create(api, text: str = POSTING, url: str | None = None, *tracks: dict):
    use_llm(fake_response(extraction(*(tracks or (track(),)))))
    return api.post("/jobs", json={"text": text, "url": url})


def test_create_job_extracts_and_saves_application(api) -> None:
    llm = use_llm(fake_response(extraction(track())))

    response = api.post("/jobs", json={"text": POSTING, "url": "https://acme.dev/vagas/1"})

    assert response.status_code == 201
    body = response.json()
    assert body["company"] == "Acme"
    assert body["title"] == "Dev Backend"
    assert body["url"] == "https://acme.dev/vagas/1"
    assert body["raw_text"] == POSTING
    assert body["tracks"][0]["required_requirements"] == ["Python", "Django"]
    assert body["tracks"][0]["work_mode"] == "remote"
    assert body["selected_track"] == 0
    assert body["needs_track_choice"] is False
    # Application created together with the job, in status "saved"
    assert body["status"] == "saved"
    assert [h["status"] for h in body["status_history"]] == ["saved"]
    # the posting went to the model inside the prompt, with the job extraction prompt
    sent = llm.sdk.messages.create.call_args.kwargs
    assert POSTING in sent["messages"][0]["content"]
    assert "One requirement per item" in sent["system"]
    assert sent["output_config"]["format"]["type"] == "json_schema"


def test_requirements_are_cleaned_in_code(api) -> None:
    messy = track(required_requirements=["  Python ", "", "python", "Django\n REST"])

    body = create(api, POSTING, None, messy).json()

    assert body["tracks"][0]["required_requirements"] == ["Python", "Django REST"]


def test_multiple_tracks_wait_for_user_choice(api) -> None:
    engineer = track(title="AI Engineer", required_requirements=["Python", "LLMs"])
    builder = track(title="AI Builder", required_requirements=["No-code"])

    body = create(api, "Vaga com duas trilhas", None, engineer, builder).json()

    assert len(body["tracks"]) == 2
    assert body["selected_track"] is None
    assert body["needs_track_choice"] is True
    assert body["title"] == "AI Engineer | AI Builder"

    chosen = api.put(f"/jobs/{body['id']}/track", json={"track": 1})

    assert chosen.status_code == 200
    assert chosen.json()["selected_track"] == 1
    assert chosen.json()["title"] == "AI Builder"
    assert chosen.json()["needs_track_choice"] is False
    assert api.get(f"/jobs/{body['id']}").json()["title"] == "AI Builder"


def test_choose_nonexistent_track_returns_422(api) -> None:
    job_id = create(api).json()["id"]
    assert api.put(f"/jobs/{job_id}/track", json={"track": 5}).status_code == 422
    assert api.put(f"/jobs/{job_id}/track", json={"track": -1}).status_code == 422


def test_invalid_model_output_saves_nothing(api) -> None:
    use_llm(fake_response('{"tracks": [{"title": "faltou o resto"'))

    response = api.post("/jobs", json={"text": POSTING})

    assert response.status_code == 502
    assert api.get("/jobs").json() == []


def test_model_returning_no_tracks_is_rejected(api) -> None:
    use_llm(fake_response(extraction()))

    assert api.post("/jobs", json={"text": POSTING}).status_code == 502
    assert api.get("/jobs").json() == []


def test_invalid_work_mode_is_rejected(api) -> None:
    use_llm(fake_response(extraction(track(work_mode="anywhere"))))
    assert api.post("/jobs", json={"text": POSTING}).status_code == 502


def test_blank_text_is_rejected_without_calling_model(api) -> None:
    llm = use_llm()

    assert api.post("/jobs", json={"text": "   "}).status_code == 422
    assert api.post("/jobs", json={"text": ""}).status_code == 422
    llm.sdk.messages.create.assert_not_called()


def test_list_jobs_filters_by_status(api, db) -> None:
    from app.models import ApplicationStatus, Job

    first = create(api, "vaga 1", None, track(title="Vaga 1")).json()
    second = create(api, "vaga 2", None, track(title="Vaga 2")).json()
    db.get(Job, first["id"]).application.set_status(ApplicationStatus.APPLIED)
    db.commit()

    all_jobs = api.get("/jobs").json()
    assert [j["title"] for j in all_jobs] == ["Vaga 2", "Vaga 1"]  # most recent first
    assert "raw_text" not in all_jobs[0]

    saved = api.get("/jobs", params={"status": "saved"}).json()
    assert [j["id"] for j in saved] == [second["id"]]
    applied = api.get("/jobs", params={"status": "applied"}).json()
    assert [j["id"] for j in applied] == [first["id"]]

    assert api.get("/jobs", params={"status": "inexistente"}).status_code == 422


def test_get_job_not_found(api) -> None:
    assert api.get("/jobs/999").status_code == 404


def test_update_application_status_and_notes(api) -> None:
    job_id = create(api).json()["id"]
    before = api.get("/jobs").json()[0]["updated_at"]

    moved = api.patch(f"/jobs/{job_id}/application", json={"status": "applied"})

    assert moved.status_code == 200
    assert moved.json()["status"] == "applied"
    assert [h["status"] for h in moved.json()["status_history"]] == ["saved", "applied"]
    assert api.get("/jobs").json()[0]["updated_at"] >= before

    noted = api.patch(f"/jobs/{job_id}/application", json={"notes": "Entrevista marcada"}).json()
    assert noted["notes"] == "Entrevista marcada"
    assert noted["status"] == "applied"  # unchanged
    # same status again does not add to the history
    again = api.patch(f"/jobs/{job_id}/application", json={"status": "applied"}).json()
    assert len(again["status_history"]) == 2

    assert api.patch(f"/jobs/{job_id}/application", json={"status": "contratado"}).status_code == 422
    assert api.patch("/jobs/999/application", json={"status": "applied"}).status_code == 404


def test_list_shows_latest_analysis_score(api, db) -> None:
    from app.models import Analysis, Job

    job_id = create(api).json()["id"]
    assert api.get("/jobs").json()[0]["score"] is None

    job = db.get(Job, job_id)
    job.analyses.append(Analysis(profile_version=1, result={"score": 40}))
    job.analyses.append(Analysis(profile_version=1, result={"score": 76}))
    db.commit()

    assert api.get("/jobs").json()[0]["score"] == 76


def test_delete_job(api) -> None:
    job_id = create(api).json()["id"]

    assert api.delete(f"/jobs/{job_id}").status_code == 204
    assert api.get(f"/jobs/{job_id}").status_code == 404
    assert api.get("/jobs").json() == []
    assert api.delete(f"/jobs/{job_id}").status_code == 404
