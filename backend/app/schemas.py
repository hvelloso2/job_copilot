"""Request/response schemas of the HTTP API."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.llm.schemas import JobData, ProfileData
from app.models import ApplicationStatus


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
    created_at: datetime


class JobOut(JobSummary):
    url: str | None
    raw_text: str
    tracks: list[JobData]
    selected_track: int | None
    status_history: list[dict[str, str]]
