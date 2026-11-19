"""Pydantic schemas for everything the LLM returns.

The JSON Schema sent to the API is generated from these models (see `strict_json_schema`),
and every response is validated against the same model in code.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Experience(_Strict):
    title: str
    company: str
    period: str | None = None
    activities: list[str] = Field(default_factory=list)


class SkillCategory(_Strict):
    category: str
    items: list[str] = Field(default_factory=list)


class Project(_Strict):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    link: str | None = None


class Education(_Strict):
    institution: str
    degree: str | None = None
    period: str | None = None


class Certification(_Strict):
    name: str
    issuer: str | None = None
    year: str | None = None


class Language(_Strict):
    language: str
    level: str | None = None


class ProfileData(_Strict):
    summary: str | None = None
    experiences: list[Experience] = Field(default_factory=list)
    skills: list[SkillCategory] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)


WorkMode = Literal["remote", "hybrid", "onsite"]


class JobData(_Strict):
    """One job posting (or one track of a posting that offers several)."""

    company: str | None = None
    title: str
    seniority: str | None = None
    work_mode: WorkMode | None = None
    location: str | None = None
    required_requirements: list[str] = Field(default_factory=list)
    preferred_requirements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    salary: str | None = None

    @field_validator(
        "required_requirements", "preferred_requirements", "technologies", "responsibilities", "benefits"
    )
    @classmethod
    def _clean_items(cls, items: list[str]) -> list[str]:
        """Strips whitespace, drops empty items and case-insensitive duplicates (keeps order)."""
        seen: set[str] = set()
        cleaned = []
        for item in items:
            item = " ".join(item.split())
            if item and item.casefold() not in seen:
                seen.add(item.casefold())
                cleaned.append(item)
        return cleaned


class JobExtraction(_Strict):
    """What the model returns for a pasted job posting: one item per track."""

    tracks: list[JobData]

    @field_validator("tracks")
    @classmethod
    def _at_least_one(cls, tracks: list[JobData]) -> list[JobData]:
        if not tracks:
            raise ValueError("a job posting must have at least one track")
        return tracks


RequirementStatus = Literal["meets", "partial", "missing"]


class RequirementAssessment(_Strict):
    # evidence and explanation come before status so the model reasons before deciding
    requirement_id: str
    evidence: str | None = None
    explanation: str
    status: RequirementStatus


class Strength(_Strict):
    point: str
    evidence: str


class ResumeSuggestion(_Strict):
    original: str
    suggested: str
    reason: str
    skills_mentioned: list[str] = Field(default_factory=list)


class JobAnalysis(_Strict):
    """What the model returns when comparing the profile with one job track. Verified in code."""

    requirements: list[RequirementAssessment]
    strengths: list[Strength] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    resume_suggestions: list[ResumeSuggestion] = Field(default_factory=list)
    study_plan: list[str] = Field(default_factory=list)


class TextDraft(_Strict):
    """A text generated for the hiring process (summary, cover letter or answer)."""

    text: str


class Claim(_Strict):
    claim: str
    evidence: str | None = None


class ClaimList(_Strict):
    """Statements about the candidate found in a generated text. Verified in code."""

    claims: list[Claim]


class FoundPosting(_Strict):
    link: int = Field(description="Number of the link in the list, e.g. 12 for [12].")
    title: str = Field(description="Job title, copied from the link text.")
    company: str | None
    location: str | None


class FoundPostings(_Strict):
    postings: list[FoundPosting]


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema for structured outputs: every object closed and every property required.

    Optional values stay expressible as `null` (anyOf with null), so the model is never
    pushed to fill a field it has no information for.
    """
    schema = model.model_json_schema()

    def walk(node: Any) -> None:
        """`node` is always a schema node, never a name->schema mapping."""
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        node.pop("title", None)  # pydantic metadata, not a field
        node.pop("default", None)
        if "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"])
            for prop_schema in node["properties"].values():
                walk(prop_schema)
        for key in ("$defs",):
            for sub in node.get(key, {}).values():
                walk(sub)
        for key in ("items", "anyOf"):
            if key in node:
                walk(node[key])

    walk(schema)
    return schema
