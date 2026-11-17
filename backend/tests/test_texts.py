"""Claim verification for generated texts, tested without HTTP or the model."""

from app.analysis import ProfileIndex
from app.llm.schemas import ClaimList, JobData
from app.texts import find_placeholders, highlight, text_warnings, verify_claims

PROFILE = {
    "summary": "Desenvolvedor Full Stack com 1,5 ano de atuação prática",
    "experiences": [
        {"title": "Dev", "company": "Ayoa", "period": "Jan/2025 – Jun/2026",
         "activities": ["Desenvolvi APIs REST com FastAPI e PostgreSQL"]},
    ],
    "skills": [{"category": "Back-end", "items": ["Python", "FastAPI"]}],
    "projects": [], "education": [], "certifications": [], "languages": [],
}
TRACK = JobData(title="Dev Backend", technologies=["Python", "FastAPI", "Docker", "Kubernetes"])
INDEX = ProfileIndex(PROFILE)


def claims(*items) -> ClaimList:
    return ClaimList.model_validate({"claims": [{"claim": c, "evidence": e} for c, e in items]})


def test_supported_claim_with_real_evidence() -> None:
    text = "Desenvolvi APIs REST com FastAPI e PostgreSQL no meu estágio."
    result = verify_claims(text, claims(("Desenvolvi APIs REST com FastAPI e PostgreSQL",
                                         "Desenvolvi APIs REST com FastAPI e PostgreSQL")), TRACK, INDEX)

    assert result[0].supported is True
    assert result[0].reason is None
    assert (result[0].start, result[0].end) == (0, 45)


def test_invented_claims_are_caught() -> None:
    text = "Tenho 3 anos de experiência com Python. Usei Docker em produção. Liderei um time."
    result = verify_claims(text, claims(
        ("Tenho 3 anos de experiência com Python", "Python"),  # evidence real, number invented
        ("Usei Docker em produção", "Docker em produção"),  # evidence invented
        ("Liderei um time", None),  # no evidence
    ), TRACK, INDEX)

    assert [c.supported for c in result] == [False, False, False]
    assert result[0].reason == "Não está no perfil: 3."
    assert "Evidência não encontrada" in result[1].reason and "Docker" in result[1].reason
    assert result[2].reason == "Sem evidência no perfil."


def test_claims_inside_placeholders_and_duplicates_are_ignored() -> None:
    text = "Quero trabalhar aqui porque [PREENCHER: motivo para esta empresa]. Uso Python."
    result = verify_claims(text, claims(
        ("motivo para esta empresa", None),
        ("Uso Python", "Python"),
        ("uso python", "Python"),
    ), TRACK, INDEX)

    assert [c.claim for c in result] == ["Uso Python"]
    assert find_placeholders(text) == ["motivo para esta empresa"]


def test_claim_not_found_in_text_has_no_position() -> None:
    result = verify_claims("Uso Python.", claims(("Trabalho com Python há anos", None)), TRACK, INDEX)
    assert result[0].start is None
    assert result[0].supported is False


def test_highlight_marks_only_unsupported_claims() -> None:
    text = "Uso Python e Docker. Tenho 3 anos de casa."
    checked = verify_claims(text, claims(("Uso Python", "Python"), ("Docker", None), ("3 anos", None)), TRACK, INDEX)

    assert highlight(text, checked) == "Uso Python e [[SEM SUPORTE: Docker]]. Tenho [[SEM SUPORTE: 3 anos]] de casa."


def test_warnings_catch_terms_the_model_did_not_list() -> None:
    text = "Uso Python e Kubernetes. Fiz 1,5 ano de estágio. [PREENCHER: 2 exemplos de resultado]"
    checked = verify_claims(text, claims(("Uso Python", "Python")), TRACK, INDEX)

    # Kubernetes was never listed as a claim, but the code still finds it; 1,5 is in the profile;
    # numbers inside placeholders are ignored
    assert text_warnings(text, TRACK, INDEX, checked) == ["Kubernetes"]


def test_warnings_do_not_repeat_terms_of_unsupported_claims() -> None:
    text = "Usei Docker. Fiz 30 deploys em 2023."
    checked = verify_claims(text, claims(("Usei Docker", None), ("Fiz 30 deploys", None)), TRACK, INDEX)

    # "3"-like substrings must not hide other numbers: 2023 is still reported
    assert text_warnings(text, TRACK, INDEX, checked) == ["2023"]
