"""Request/response schemas of the HTTP API."""

from datetime import datetime

from pydantic import BaseModel

from app.llm.schemas import ProfileData


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
