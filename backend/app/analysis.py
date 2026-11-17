"""Verification and scoring of a job analysis.

Everything here is plain code on purpose: the model's answer is never trusted on its own.
- Evidence must be an excerpt that really exists in the saved profile; otherwise the
  requirement is downgraded to "missing".
- Résumé suggestions are scanned for skills and numbers that are not in the profile.
- The compatibility score is computed here with fixed weights, not by the model.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.llm.schemas import JobAnalysis, JobData
from app.schemas import (
    AnalysisResult,
    RequirementKind,
    RequirementResult,
    StrengthResult,
    SuggestionResult,
    VerificationStats,
)

KIND_WEIGHT: dict[str, float] = {"required": 2.0, "preferred": 1.0}
STATUS_VALUE: dict[str, float] = {"meets": 1.0, "partial": 0.5, "missing": 0.0}

# Labels used in prompts (Portuguese, like the job postings)
KIND_LABEL = {"required": "obrigatório", "preferred": "desejável"}
STATUS_LABEL = {"meets": "atende", "partial": "parcial", "missing": "não atende"}

NOTE_EVIDENCE_NOT_FOUND = "Evidência não encontrada no perfil."
NOTE_NO_EVIDENCE = "Sem evidência no perfil."
NOTE_NOT_ASSESSED = "O modelo não avaliou este requisito."

_CHAR_MAP = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "–": "-", "—": "-", " ": " ",
})
_EDGE_CHARS = " \t\n.,;:!?\"'()[]-*•"
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")


def normalize(text: str) -> str:
    """Case- and whitespace-insensitive form used for every comparison (also unifies quotes/dashes)."""
    text = unicodedata.normalize("NFKC", text).translate(_CHAR_MAP).casefold()
    return " ".join(text.split())


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def _contains_words(normalized_text: str, normalized_term: str) -> bool:
    """Whole-word search: "java" is not found in "javascript", nor "git" in "github"."""
    return re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", normalized_text) is not None


def mentions_word(normalized_text: str, term: str) -> bool:
    term = normalize(term).strip(_EDGE_CHARS)
    return bool(term) and _contains_words(normalized_text, term)


class ProfileIndex:
    """Searchable view of the saved profile (only the reviewed data, not the raw résumé text)."""

    def __init__(self, profile_data: dict[str, Any]) -> None:
        self.fields = [f for f in (normalize(s) for s in _strings(profile_data)) if f]
        self._full = "\n".join(self.fields)

    def contains_excerpt(self, excerpt: str | None) -> bool:
        """True if the excerpt is inside a single profile value, on word boundaries.

        "..." may separate parts of that value. Word boundaries matter for short evidence:
        "Git" must not be accepted because the profile says "GitHub".
        """
        if not excerpt:
            return False
        parts = [p.strip(_EDGE_CHARS) for p in normalize(excerpt).split("...")]
        parts = [p for p in parts if p]
        if not parts:
            return False
        return any(all(_contains_words(field, part) for part in parts) for field in self.fields)

    def mentions(self, term: str) -> bool:
        return mentions_word(self._full, term)


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    kind: RequirementKind


def numbered_requirements(track: JobData) -> list[Requirement]:
    """Requirements with stable ids (R1.. required, P1.. preferred). Their text always comes from here."""
    return [
        *(Requirement(f"R{i}", text, "required") for i, text in enumerate(track.required_requirements, start=1)),
        *(Requirement(f"P{i}", text, "preferred") for i, text in enumerate(track.preferred_requirements, start=1)),
    ]


def compute_score(requirements: list[RequirementResult]) -> int | None:
    """Weighted average of the verified statuses, 0-100. Required items weigh twice as much as preferred."""
    total = sum(KIND_WEIGHT[r.kind] for r in requirements)
    if not total:
        return None
    earned = sum(KIND_WEIGHT[r.kind] * STATUS_VALUE[r.status] for r in requirements)
    return round(100 * earned / total)


def _verify_requirements(
    requirements: list[Requirement], output: JobAnalysis, index: ProfileIndex
) -> tuple[list[RequirementResult], int, int]:
    assessments = {}
    for item in output.requirements:
        assessments.setdefault(item.requirement_id.strip().upper(), item)  # first answer per id wins

    results, rejected, not_assessed = [], 0, 0
    for req in requirements:
        item = assessments.get(req.id)
        if item is None:
            not_assessed += 1
            results.append(RequirementResult(
                requirement=req.text, kind=req.kind, status="missing", model_status=None,
                evidence=None, evidence_verified=False, explanation="", note=NOTE_NOT_ASSESSED,
            ))
            continue

        evidence = (item.evidence or "").strip() or None
        verified = index.contains_excerpt(evidence)
        status, note = item.status, None
        if item.status != "missing" and not verified:
            status = "missing"
            if evidence:
                note = NOTE_EVIDENCE_NOT_FOUND
                rejected += 1
            else:
                note = NOTE_NO_EVIDENCE
        results.append(RequirementResult(
            requirement=req.text, kind=req.kind, status=status, model_status=item.status,
            evidence=evidence, evidence_verified=verified, explanation=item.explanation, note=note,
        ))
    return results, rejected, not_assessed


def unsupported_terms(suggested: str, skills: list[str], job_technologies: list[str], index: ProfileIndex) -> list[str]:
    """Skills/technologies and numbers in a suggested text that the profile does not have.

    Checks the skills the model says it used, plus every job technology that appears in the
    text (so a skill the model "forgot" to list is still caught), plus every number.
    """
    text = normalize(suggested)
    candidates = [*skills, *(t for t in job_technologies if len(t.strip()) >= 2 and mentions_word(text, t))]
    candidates += _NUMBER_RE.findall(text)

    unsupported, seen = [], set()
    for term in candidates:
        key = normalize(term)
        if key and key not in seen and not index.mentions(term):
            seen.add(key)
            unsupported.append(term.strip())
    return unsupported


def build_analysis(
    output: JobAnalysis, track_index: int, track: JobData, profile_data: dict[str, Any]
) -> AnalysisResult:
    """Turns the raw model output into the verified, scored analysis that gets saved."""
    index = ProfileIndex(profile_data)
    requirements, rejected, not_assessed = _verify_requirements(numbered_requirements(track), output, index)

    strengths = [
        StrengthResult(point=s.point, evidence=s.evidence, evidence_verified=index.contains_excerpt(s.evidence))
        for s in output.strengths
    ]
    suggestions = [
        SuggestionResult(
            original=s.original,
            suggested=s.suggested,
            reason=s.reason,
            original_found=index.contains_excerpt(s.original),
            unsupported=unsupported_terms(s.suggested, s.skills_mentioned, track.technologies, index),
        )
        for s in output.resume_suggestions
    ]

    return AnalysisResult(
        track=track_index,
        track_title=track.title,
        score=compute_score(requirements),
        requirements=requirements,
        strengths=strengths,
        gaps=output.gaps,
        resume_suggestions=suggestions,
        study_plan=output.study_plan,
        verification=VerificationStats(
            evidence_rejected=rejected,
            requirements_not_assessed=not_assessed,
            strengths_rejected=sum(not s.evidence_verified for s in strengths),
            suggestions_flagged=sum(bool(s.unsupported) or not s.original_found for s in suggestions),
        ),
    )
