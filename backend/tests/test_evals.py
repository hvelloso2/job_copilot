"""The evaluation scoring and pipeline, with the Claude client mocked (no API calls)."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_llm_client
from app.main import app
from evals import run_evals, scoring
from tests.helpers import fake_llm, fake_response

EXPECTED = {
    "tracks": 1,
    "required": [
        {"text": "Python", "match": ["python"]},
        {"text": "PostgreSQL", "match": ["postgres"]},
        {"text": "Testes", "match": ["teste"]},
    ],
    "preferred": [{"text": "Kubernetes", "match": ["kubernetes"]}],
    "analysis": [
        {"match": ["python"], "expected": "meets"},
        {"match": ["kubernetes"], "expected": "missing"},
    ],
}


def track(required, preferred=(), title="Dev") -> dict:
    return {
        "company": "Acme", "title": title, "seniority": None, "work_mode": None, "location": None,
        "required_requirements": list(required), "preferred_requirements": list(preferred),
        "technologies": [], "responsibilities": [], "benefits": [], "salary": None,
    }


def test_fold_ignores_case_and_accents() -> None:
    assert scoring.fold("  Estatística  BÁSICA ") == "estatistica basica"
    assert scoring.matches("Inglês fluente", ["ingles"])


def test_extraction_coverage_precision_and_kind() -> None:
    extracted = track(
        ["Experiência com Python", "PostgreSQL", "Kubernetes"],  # Kubernetes should be preferred
        ["Boa comunicação"],                                      # not in the posting's gabarito
    )

    score = scoring.score_extraction(extracted, EXPECTED, n_tracks=1)

    assert (score.found, score.expected) == (3, 4)
    assert score.missed == ["Testes"]
    assert (score.extracted_valid, score.extracted) == (3, 4)
    assert score.invented == ["Boa comunicação"]
    assert score.wrong_kind == ["Kubernetes"]
    assert score.coverage == 0.75 and score.precision == 0.75
    assert score.tracks_ok


def test_wrong_number_of_tracks_is_reported() -> None:
    assert not scoring.score_extraction(track(["Python"]), {**EXPECTED, "tracks": 2}, n_tracks=1).tracks_ok


def test_pick_track_by_title_hint() -> None:
    tracks = [track([], title="Analista de Dados Júnior"), track([], title="Desenvolvedor(a) Backend Júnior")]
    assert scoring.pick_track(tracks, "backend") == 1
    assert scoring.pick_track(tracks, None) is None
    assert scoring.pick_track(tracks[:1], None) == 0


def test_analysis_cases() -> None:
    requirements = [
        {"requirement": "Python", "status": "meets"},
        {"requirement": "Kubernetes", "status": "partial"},
    ]
    cases = scoring.score_analysis(requirements, EXPECTED["analysis"] + [{"match": ["go"], "expected": "missing"}])

    assert [c.correct for c in cases] == [True, False, False]
    assert cases[2].requirement is None


def test_planted_caught_by_claim_or_warning_and_false_alarms() -> None:
    case = {
        "fabricated": ["5 anos de Kubernetes", "liderei uma equipe de 8 pessoas", "artigo na SBC"],
        "true": ["trabalho com Python"],
    }
    claims = [
        {"claim": "Tenho 5 anos de Kubernetes", "supported": False},  # contains the snippet
        {"claim": "trabalho com Python", "supported": False},          # true statement flagged
    ]

    score = scoring.score_planted(case, claims, warnings=["8"])  # number warning inside the 2nd snippet

    assert (score.caught, score.fabricated) == (2, 3)
    assert score.missed == ["artigo na SBC"]
    assert score.false_alarms == 1


def test_cost_summary_averages_per_operation() -> None:
    call = lambda op, i, o: SimpleNamespace(operation=op, model="claude-haiku-5-5", input_tokens=i, output_tokens=o, duration_s=2.0)
    rows = scoring.cost_summary([call("extract_job", 1000, 200), call("extract_job", 3000, 400), call("x", 1, 1)])

    extract = rows[0]
    assert (extract["calls"], extract["input_tokens"], extract["output_tokens"]) == (2, 2000, 300)
    assert extract["cost_usd"] == pytest.approx((2000 * 0.10 + 300 * 0.50) / 1_000_000)


def test_call_cost_uses_each_call_model() -> None:
    haiku = SimpleNamespace(model="claude-haiku-5-5", input_tokens=1_000_000, output_tokens=0)
    sonnet = SimpleNamespace(model="claude-sonnet-5-5-20261001", input_tokens=0, output_tokens=1_000_000)
    assert scoring.call_cost(haiku) == pytest.approx(0.10)
    assert scoring.call_cost(sonnet) == pytest.approx(10.00)
    assert scoring.call_cost(SimpleNamespace(model="other", input_tokens=1, output_tokens=1)) is None


def test_describe_models_lists_overrides() -> None:
    llm = run_evals.make_client("claude-opus-5-5", "", "extract_job=claude-haiku-5-5, analyze_job=claude-haiku-5-5")
    assert run_evals.describe_models(llm) == "claude-opus-5-5 (extract_job, analyze_job: claude-haiku-5-5)"
    assert run_evals.describe_models(run_evals.make_client("claude-opus-5-5", "")) == "claude-opus-5-5"


def test_cost_unknown_model_is_none() -> None:
    call = SimpleNamespace(operation="op", model="other-model", input_tokens=1, output_tokens=1, duration_s=1.0)
    assert scoring.cost_summary([call])[0]["cost_usd"] is None


def test_fixtures_are_consistent() -> None:
    profile, jobs, planted = run_evals.load_fixtures(None)
    assert profile["experiences"] and len(jobs) == 10
    for job in jobs:
        expected = job["expected"]
        assert expected["required"], job["id"]
        for entry in expected["required"] + expected.get("preferred", []):
            # every expected requirement must really be written in the posting
            assert scoring.matches(job["text"], entry["match"]), f"{job['id']}: {entry['text']}"
        for case in expected.get("analysis", []):
            assert case["expected"] in ("meets", "partial", "missing")
    for case in planted["texts"]:
        for snippet in case["fabricated"] + case["true"]:
            assert scoring.fold(snippet) in scoring.fold(case["text"])


def test_run_job_through_the_api_with_mocked_claude(db) -> None:
    profile, *_ = run_evals.load_fixtures(None)
    extraction = {"tracks": [track(["Python", "PostgreSQL", "Testes"], ["Kubernetes"])]}
    analysis = {"requirements": [
        {"requirement_id": "R1", "evidence": "Python", "explanation": "ok", "status": "meets"},
        {"requirement_id": "R2", "evidence": "PostgreSQL", "explanation": "ok", "status": "meets"},
        {"requirement_id": "R3", "evidence": "Testes automatizados com pytest", "explanation": "ok", "status": "meets"},
        {"requirement_id": "P1", "evidence": None, "explanation": "não tem", "status": "missing"},
    ]}
    llm = fake_llm(
        fake_response(json.dumps(extraction)),
        fake_response(json.dumps(analysis)),
        fake_response(json.dumps({"text": "Uso Python há 9 anos."})),
        fake_response(json.dumps({"claims": [{"claim": "Uso Python há 9 anos", "evidence": None}]})),
    )
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_llm_client] = lambda: llm
    try:
        with TestClient(app) as api:
            api.put("/profile", json={"data": profile, "raw_text": ""}).raise_for_status()
            result = run_evals.run_job(api, {"id": "x", "text": "vaga", "expected": EXPECTED}, with_texts=True)
    finally:
        app.dependency_overrides.clear()

    assert result["errors"] == []
    assert result["extraction"]["coverage"] == 1.0
    assert [c["correct"] for c in result["analysis_cases"]] == [True, True]
    assert result["text"]["unsupported"] == 1
    summary = run_evals.summarize([result], [], scoring.cost_summary(llm.calls))
    assert summary["coverage"] == 1.0 and summary["analysis_accuracy"] == 1.0
    assert "| x | 100% | 100% | 2/2 |" in run_evals.render_run({
        "model": "test-model", "started": "2026-11-18 10:00", "label": "", "seconds": 1.0,
        "fixtures_reviewed": False, "jobs": [result], "planted": [], "costs": [], "total_cost": None,
        "summary": summary,
    })
