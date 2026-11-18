"""Request/response schemas of the HTTP API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.llm.schemas import JobData, ProfileData, RequirementStatus
from app.models import ApplicationStatus, TextFormat, TextType


class ProfileDraft(BaseModel):
    """Extracted profile returned for review. Nothing is saved yet."""

    data: ProfileData
    raw_text: str


class ProfileSave(BaseModel):
    data: ProfileData
    raw_text: str = ""


class ProfileOut(BaseModel):
    data: ProfileData
    raw_text: str
    version: int
    updated_at: datetime


class JobCreate(BaseModel):
    text: str = Field(min_length=1, max_length=50_000, description="Texto da vaga, colado como está.")
    url: str | None = Field(default=None, max_length=1000, description="Link da vaga, só para guardar.")


class TrackChoice(BaseModel):
    track: int = Field(ge=0, description="Índice da trilha em `tracks`.")


class JobSummary(BaseModel):
    id: int
    company: str
    title: str
    status: ApplicationStatus
    needs_track_choice: bool
    score: int | None = Field(description="Nota da análise mais recente, se houver.")
    created_at: datetime
    updated_at: datetime = Field(description="Última atualização da candidatura (status ou notas).")


class JobOut(JobSummary):
    url: str | None
    raw_text: str
    tracks: list[JobData]
    selected_track: int | None
    status_history: list[dict[str, str]]
    notes: str


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = Field(default=None, max_length=20_000)


# --- Analysis (Etapa 4). Built in code from the model output, after verification. ---

RequirementKind = Literal["required", "preferred"]


class RequirementResult(BaseModel):
    requirement: str
    kind: RequirementKind
    status: RequirementStatus
    model_status: RequirementStatus | None = Field(description="O que o modelo disse, antes da verificação.")
    evidence: str | None
    evidence_verified: bool
    explanation: str
    note: str | None = Field(default=None, description="Por que o status foi rebaixado, se foi.")


class StrengthResult(BaseModel):
    point: str
    evidence: str
    evidence_verified: bool


class SuggestionResult(BaseModel):
    original: str
    suggested: str
    reason: str
    original_found: bool
    unsupported: list[str] = Field(description="Skills ou números da sugestão que não estão no perfil.")


class VerificationStats(BaseModel):
    evidence_rejected: int
    requirements_not_assessed: int
    strengths_rejected: int
    suggestions_flagged: int


class AnalysisResult(BaseModel):
    track: int
    track_title: str
    score: int | None = Field(description="0 a 100, calculada em código. Null se a vaga não tem requisitos.")
    requirements: list[RequirementResult]
    strengths: list[StrengthResult]
    gaps: list[str]
    resume_suggestions: list[SuggestionResult]
    study_plan: list[str]
    verification: VerificationStats


class AnalysisOut(AnalysisResult):
    id: int
    job_id: int
    profile_version: int
    outdated: bool = Field(description="O perfil mudou depois desta análise.")
    created_at: datetime


# --- Texts for the hiring process (Etapa 5) ---


class TextCreate(BaseModel):
    type: TextType
    question: str | None = Field(default=None, max_length=2000, description="Obrigatória quando type é 'answer'.")
    format: TextFormat = Field(default=TextFormat.WRITTEN, description="Só se aplica a 'answer'.")

    @model_validator(mode="after")
    def _check_fields(self) -> "TextCreate":
        self.question = (self.question or "").strip() or None
        if self.type == TextType.ANSWER and not self.question:
            raise ValueError("Envie a pergunta do processo seletivo em 'question'.")
        if self.type != TextType.ANSWER:
            if self.question:
                raise ValueError("'question' só é usada quando type é 'answer'.")
            if self.format != TextFormat.WRITTEN:
                raise ValueError("O roteiro para áudio só existe para respostas (type 'answer').")
        return self


class ClaimResult(BaseModel):
    claim: str
    evidence: str | None
    supported: bool
    reason: str | None = Field(description="Por que a afirmação não tem suporte, se não tiver.")
    start: int | None = Field(description="Posição da afirmação no texto (None se não foi localizada).")
    end: int | None


class TextVerification(BaseModel):
    highlighted_text: str = Field(description="O texto com as afirmações sem suporte marcadas como [[SEM SUPORTE: ...]].")
    placeholders: list[str] = Field(description="O que falta preencher ([PREENCHER: ...]).")
    claims: list[ClaimResult]
    unsupported_claims: int
    warnings: list[str] = Field(description="Skills ou números do texto que não estão no perfil, mesmo fora das afirmações.")
    profile_version: int
    analysis_id: int


class TextOut(TextVerification):
    id: int
    job_id: int
    type: TextType
    format: TextFormat
    question: str | None
    text: str
    created_at: datetime


# --- Dashboard (Etapa 7). Computed in code, no LLM call. ---


class SkillDemand(BaseModel):
    name: str
    count: int = Field(description="Quantas vagas salvas pedem esta skill.")
    share: int = Field(description="Porcentagem das vagas (0 a 100).")
    in_profile: bool


class FunnelStep(BaseModel):
    status: ApplicationStatus
    current: int = Field(description="Candidaturas com este status agora.")
    reached: int = Field(description="Candidaturas que chegaram a esta etapa ou passaram dela.")
    rate_from_previous: int | None = Field(description="reached desta etapa / reached da anterior, em %.")


class StatusScore(BaseModel):
    status: ApplicationStatus
    average: int | None = Field(description="Nota média da análise mais recente. Null se nenhuma foi analisada.")
    analyzed: int
    total: int


class Insights(BaseModel):
    total_jobs: int
    has_profile: bool
    skills: list[SkillDemand]
    top_gaps: list[SkillDemand] = Field(description="Skills mais pedidas que não estão no perfil.")
    funnel: list[FunnelStep]
    scores_by_status: list[StatusScore]
