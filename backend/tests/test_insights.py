import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.insights import SYNONYMS, build_insights, skill_key
from app.main import app
from app.models import Analysis, Application, ApplicationStatus, Job, Profile

PROFILE = {
    "summary": "Desenvolvedor backend.",
    "experiences": [{"title": "Dev", "company": "X", "period": None, "activities": ["APIs com Postgres"]}],
    "skills": [{"category": "Backend", "items": ["Python", "ReactJS"]}],
    "projects": [],
    "education": [],
    "certifications": [],
    "languages": [],
}


def track(technologies: list[str], title: str = "Dev") -> dict:
    return {
        "company": "Acme", "title": title, "seniority": None, "work_mode": None, "location": None,
        "required_requirements": [], "preferred_requirements": [], "technologies": technologies,
        "responsibilities": [], "benefits": [], "salary": None,
    }


def add_job(db, technologies=(), status=ApplicationStatus.SAVED, history=(), score=None, tracks=None, selected=0):
    job = Job(
        raw_text="vaga",
        extracted={"tracks": tracks or [track(list(technologies))], "selected_track": selected},
    )
    application = Application(job=job, status=status)
    application.status_history = [{"status": s.value, "at": "2026-11-01T00:00:00"} for s in (*history, status)]
    if score is not None:
        job.analyses.append(Analysis(profile_version=1, result={"score": score}))
    db.add(job)
    db.commit()
    return job


def all_jobs(db) -> list[Job]:
    return db.query(Job).all()


def test_synonyms_are_grouped_under_the_canonical_name() -> None:
    assert skill_key("Postgres") == skill_key("postgresql") == "PostgreSQL"
    assert skill_key("React.js") == skill_key("ReactJS") == "React"
    assert skill_key("  python ") == "Python"
    assert skill_key("Elixir") == "elixir"  # not in the table: just normalized


def test_no_alias_points_to_two_canonical_names() -> None:
    seen: dict[str, str] = {}
    for canonical, aliases in SYNONYMS.items():
        for name in [canonical, *aliases]:
            key = name.casefold()
            assert seen.setdefault(key, canonical) == canonical, f"{name} em {seen[key]} e {canonical}"


def test_skills_counted_once_per_job_and_sorted(db) -> None:
    add_job(db, ["Postgres", "PostgreSQL", "Docker"])  # same skill twice in one job
    add_job(db, ["postgresql", "React.js"])
    add_job(db, ["Elixir"])

    insights = build_insights(all_jobs(db), PROFILE)

    names = [(s.name, s.count, s.share) for s in insights.skills]
    assert names[0] == ("PostgreSQL", 2, 67)
    assert {n for n, *_ in names[1:]} == {"Docker", "React", "Elixir"}
    assert all(c == 1 for _, c, _ in names[1:])


def test_in_profile_uses_synonyms_and_gaps_list_the_rest(db) -> None:
    add_job(db, ["PostgreSQL", "React", "Kubernetes", "Python"])
    add_job(db, ["K8s"])

    insights = build_insights(all_jobs(db), PROFILE)

    in_profile = {s.name: s.in_profile for s in insights.skills}
    assert in_profile == {"PostgreSQL": True, "React": True, "Python": True, "Kubernetes": False}
    assert [g.name for g in insights.top_gaps] == ["Kubernetes"]
    assert insights.top_gaps[0].count == 2


def test_without_profile_every_skill_is_a_gap(db) -> None:
    add_job(db, ["Python"])

    insights = build_insights(all_jobs(db), None)

    assert insights.has_profile is False
    assert [g.name for g in insights.top_gaps] == ["Python"]


def test_job_without_chosen_track_counts_all_tracks(db) -> None:
    add_job(db, tracks=[track(["Python"], "Back"), track(["React", "Python"], "Front")], selected=None)
    add_job(db, tracks=[track(["Go"], "Back"), track(["Vue"], "Front")], selected=1)

    insights = build_insights(all_jobs(db), PROFILE)

    counts = {s.name: s.count for s in insights.skills}
    assert counts == {"Python": 1, "React": 1, "Vue.js": 1}


def test_funnel_counts_reached_stages_and_rates(db) -> None:
    S = ApplicationStatus
    add_job(db, status=S.SAVED)
    add_job(db, status=S.APPLIED, history=[S.SAVED])
    add_job(db, status=S.INTERVIEW, history=[S.SAVED, S.APPLIED])  # skipped the test step
    add_job(db, status=S.CLOSED, history=[S.SAVED, S.APPLIED, S.TEST])  # rejected after the test

    funnel = {step.status: step for step in build_insights(all_jobs(db), PROFILE).funnel}

    assert [(funnel[s].current, funnel[s].reached) for s in (S.SAVED, S.APPLIED, S.TEST, S.INTERVIEW, S.OFFER)] == [
        (1, 4), (1, 3), (0, 2), (1, 1), (0, 0)
    ]
    assert funnel[S.SAVED].rate_from_previous is None
    assert funnel[S.APPLIED].rate_from_previous == 75
    assert funnel[S.TEST].rate_from_previous == 67
    assert funnel[S.INTERVIEW].rate_from_previous == 50
    assert funnel[S.OFFER].rate_from_previous == 0
    assert funnel[S.CLOSED].current == 1


def test_average_score_per_status_uses_latest_analysis(db) -> None:
    job = add_job(db, status=ApplicationStatus.APPLIED, score=40)
    job.analyses.append(Analysis(profile_version=2, result={"score": 80}))  # newer analysis wins
    db.commit()
    add_job(db, status=ApplicationStatus.APPLIED, score=61)
    add_job(db, status=ApplicationStatus.APPLIED)  # not analyzed

    scores = {s.status: s for s in build_insights(all_jobs(db), PROFILE).scores_by_status}

    assert scores[ApplicationStatus.APPLIED].average == 70  # mean(80, 61) = 70.5 -> 70 (banker's rounding)
    assert scores[ApplicationStatus.APPLIED].analyzed == 2
    assert scores[ApplicationStatus.APPLIED].total == 3
    assert scores[ApplicationStatus.OFFER].average is None


@pytest.fixture
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_get_insights_endpoint(api, db) -> None:
    db.add(Profile(data=PROFILE, raw_text=""))
    add_job(db, ["Postgres", "Kubernetes"], score=50)

    response = api.get("/insights")

    assert response.status_code == 200
    body = response.json()
    assert body["total_jobs"] == 1
    assert body["has_profile"] is True
    assert [g["name"] for g in body["top_gaps"]] == ["Kubernetes"]
    assert len(body["funnel"]) == 6
    assert body["scores_by_status"][0] == {"status": "saved", "average": 50, "analyzed": 1, "total": 1}


def test_get_insights_with_no_data(api) -> None:
    body = api.get("/insights").json()

    assert body["total_jobs"] == 0
    assert body["skills"] == [] and body["top_gaps"] == []
    assert all(step["reached"] == 0 and step["rate_from_previous"] is None for step in body["funnel"])
