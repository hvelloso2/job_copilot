"""Verification and scoring rules, tested without HTTP or the model."""

from app.analysis import (
    NOTE_EVIDENCE_NOT_FOUND,
    NOTE_NO_EVIDENCE,
    NOTE_NOT_ASSESSED,
    ProfileIndex,
    build_analysis,
    compute_score,
    numbered_requirements,
    unsupported_terms,
)
from app.llm.schemas import JobAnalysis, JobData
from app.schemas import RequirementResult

PROFILE = {
    "summary": "Desenvolvedor backend com foco em APIs",
    "experiences": [
        {
            "title": "Desenvolvedor Python",
            "company": "Ayoa",
            "period": "2023 - 2024",
            "activities": ["Desenvolvi APIs REST com FastAPI e PostgreSQL", "Reduzi o tempo de resposta em 30%"],
        }
    ],
    "skills": [{"category": "Linguagens", "items": ["Python", "JavaScript"]}],
    "projects": [],
    "education": [],
    "certifications": [],
    "languages": [],
}

TRACK = JobData(
    title="Dev Backend",
    required_requirements=["Python", "APIs REST", "Docker"],
    preferred_requirements=["AWS"],
    technologies=["Python", "FastAPI", "Docker", "AWS", "Java"],
)


def assessment(req_id, status, evidence=None, explanation="ok"):
    return {"requirement_id": req_id, "evidence": evidence, "explanation": explanation, "status": status}


def analysis(requirements, **extra) -> JobAnalysis:
    return JobAnalysis.model_validate({"requirements": requirements, **extra})


# --- ProfileIndex ---

def test_excerpt_found_ignoring_case_spaces_and_edges() -> None:
    index = ProfileIndex(PROFILE)
    assert index.contains_excerpt("Desenvolvi APIs REST com FastAPI")
    assert index.contains_excerpt("  desenvolvi   apis rest  ")
    assert index.contains_excerpt('"Python".')


def test_excerpt_with_ellipsis_must_stay_in_one_field() -> None:
    index = ProfileIndex(PROFILE)
    assert index.contains_excerpt("Desenvolvi APIs ... PostgreSQL")
    # parts from two different values do not count as one excerpt
    assert not index.contains_excerpt("Desenvolvedor Python ... Ayoa")


def test_excerpt_must_match_whole_words() -> None:
    index = ProfileIndex({**PROFILE, "skills": [{"category": "Ferramentas", "items": ["GitHub", "JavaScript"]}]})
    assert index.contains_excerpt("GitHub")
    assert not index.contains_excerpt("Git")
    assert not index.contains_excerpt("Java")
    assert not index.contains_excerpt("APIs RES")


def test_invented_or_paraphrased_excerpt_not_found() -> None:
    index = ProfileIndex(PROFILE)
    assert not index.contains_excerpt("Desenvolvi APIs REST com Django")
    assert not index.contains_excerpt("5 anos de experiência com Docker")
    assert not index.contains_excerpt("")
    assert not index.contains_excerpt(None)
    assert not index.contains_excerpt("...")


def test_mentions_uses_whole_words() -> None:
    index = ProfileIndex(PROFILE)
    assert index.mentions("python")
    assert index.mentions("FastAPI")
    assert not index.mentions("Java")  # only "JavaScript" is in the profile
    assert index.mentions("30")
    assert not index.mentions("50")


# --- scoring ---

def _req(kind, status) -> RequirementResult:
    return RequirementResult(requirement="x", kind=kind, status=status, model_status=status,
                             evidence=None, evidence_verified=False, explanation="")


def test_score_weights_required_twice_preferred() -> None:
    assert compute_score([_req("required", "meets"), _req("preferred", "missing")]) == 67  # 2/3
    assert compute_score([_req("required", "missing"), _req("preferred", "meets")]) == 33  # 1/3
    assert compute_score([_req("required", "partial")]) == 50
    assert compute_score([_req("required", "meets"), _req("required", "meets")]) == 100
    assert compute_score([]) is None


def test_requirements_are_numbered_by_kind() -> None:
    reqs = numbered_requirements(TRACK)
    assert [(r.id, r.text, r.kind) for r in reqs] == [
        ("R1", "Python", "required"),
        ("R2", "APIs REST", "required"),
        ("R3", "Docker", "required"),
        ("P1", "AWS", "preferred"),
    ]


# --- build_analysis: the verification itself ---

def test_invented_evidence_is_caught_and_downgraded() -> None:
    output = analysis([
        assessment("R1", "meets", "Python"),
        assessment("R2", "meets", "Desenvolvi APIs REST com FastAPI"),
        assessment("R3", "meets", "Experiência com Docker em produção"),  # invented
        assessment("P1", "partial", "Usei AWS Lambda"),  # invented
    ])

    result = build_analysis(output, 0, TRACK, PROFILE)

    by_text = {r.requirement: r for r in result.requirements}
    assert by_text["Python"].status == "meets"
    assert by_text["Python"].evidence_verified is True
    docker = by_text["Docker"]
    assert docker.status == "missing"
    assert docker.model_status == "meets"
    assert docker.evidence_verified is False
    assert docker.note == NOTE_EVIDENCE_NOT_FOUND
    assert by_text["AWS"].status == "missing"
    assert result.verification.evidence_rejected == 2
    # score uses the verified statuses: 2 of 3 required met, preferred missing -> 4/7
    assert result.score == 57


def test_met_without_evidence_is_downgraded() -> None:
    output = analysis([assessment("R1", "meets", None), assessment("R2", "partial", "  ")])

    result = build_analysis(output, 0, TRACK, PROFILE)

    assert [r.status for r in result.requirements[:2]] == ["missing", "missing"]
    assert result.requirements[0].note == NOTE_NO_EVIDENCE
    assert result.verification.evidence_rejected == 0


def test_requirement_text_comes_from_job_and_missing_ids_are_filled() -> None:
    output = analysis([
        assessment("r1", "meets", "Python"),  # id case is tolerated
        assessment("R1", "missing"),  # duplicate: first answer wins
        assessment("X9", "meets", "Python"),  # unknown id: ignored
    ])

    result = build_analysis(output, 0, TRACK, PROFILE)

    assert [r.requirement for r in result.requirements] == ["Python", "APIs REST", "Docker", "AWS"]
    assert result.requirements[0].status == "meets"
    assert all(r.note == NOTE_NOT_ASSESSED for r in result.requirements[1:])
    assert result.verification.requirements_not_assessed == 3


def test_missing_with_evidence_stays_missing() -> None:
    result = build_analysis(analysis([assessment("R1", "missing", "Python")]), 0, TRACK, PROFILE)
    assert result.requirements[0].status == "missing"
    assert result.requirements[0].note is None


def test_strengths_are_verified() -> None:
    output = analysis(
        [],
        strengths=[
            {"point": "APIs com FastAPI", "evidence": "Desenvolvi APIs REST com FastAPI e PostgreSQL"},
            {"point": "Liderança", "evidence": "Liderei um time de 5 pessoas"},
        ],
    )

    result = build_analysis(output, 0, TRACK, PROFILE)

    assert [s.evidence_verified for s in result.strengths] == [True, False]
    assert result.verification.strengths_rejected == 1


def test_suggestion_rewording_real_facts_is_clean() -> None:
    unsupported = unsupported_terms(
        "Construí APIs REST em Python com FastAPI e PostgreSQL, reduzindo o tempo de resposta em 30%",
        ["Python", "FastAPI", "PostgreSQL"], TRACK.technologies, ProfileIndex(PROFILE),
    )
    assert unsupported == []


def test_suggestion_with_invented_skill_or_number_is_flagged() -> None:
    index = ProfileIndex(PROFILE)
    # skill declared by the model
    assert unsupported_terms("APIs com FastAPI e Kubernetes", ["FastAPI", "Kubernetes"], [], index) == ["Kubernetes"]
    # job technology the model did not declare is still caught
    assert unsupported_terms("APIs em Python com Docker", ["Python"], TRACK.technologies, index) == ["Docker"]
    # invented number
    assert unsupported_terms("Reduzi o tempo de resposta em 50%", [], [], index) == ["50"]


def test_suggestion_original_must_exist() -> None:
    output = analysis(
        [],
        resume_suggestions=[
            {"original": "Desenvolvi APIs REST com FastAPI e PostgreSQL",
             "suggested": "Desenvolvi APIs REST de alta performance com FastAPI e PostgreSQL",
             "reason": "usa o vocabulário da vaga", "skills_mentioned": ["FastAPI", "PostgreSQL"]},
            {"original": "Trabalhei com microsserviços",
             "suggested": "Projetei microsserviços com Docker e AWS",
             "reason": "x", "skills_mentioned": ["Docker", "AWS"]},
        ],
    )

    result = build_analysis(output, 0, TRACK, PROFILE)

    good, bad = result.resume_suggestions
    assert good.original_found and good.unsupported == []
    assert not bad.original_found
    assert bad.unsupported == ["Docker", "AWS"]
    assert result.verification.suggestions_flagged == 1
