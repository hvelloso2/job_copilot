import enum
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApplicationStatus(str, enum.Enum):
    SAVED = "saved"          # salva
    APPLIED = "applied"      # aplicada
    TEST = "test"            # teste
    INTERVIEW = "interview"  # entrevista
    OFFER = "offer"          # oferta
    CLOSED = "closed"        # encerrada


class TextType(str, enum.Enum):
    SUMMARY = "summary"        # resumo
    COVER_LETTER = "cover_letter"  # carta
    ANSWER = "answer"          # resposta


class TextFormat(str, enum.Enum):
    WRITTEN = "written"            # texto escrito
    AUDIO_SCRIPT = "audio_script"  # roteiro para áudio


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    raw_text: Mapped[str] = mapped_column(Text)
    extracted: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    application: Mapped["Application | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    generated_texts: Mapped[list["GeneratedText"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True)
    status: Mapped[ApplicationStatus] = mapped_column(Enum(ApplicationStatus), default=ApplicationStatus.SAVED)
    # Lista de {"status": ..., "at": ISO datetime} com cada mudança de status
    status_history: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    job: Mapped[Job] = relationship(back_populates="application")

    def set_status(self, status: ApplicationStatus) -> None:
        self.status = status
        self.status_history = [*(self.status_history or []), {"status": status.value, "at": utcnow().isoformat()}]


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    profile_version: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="analyses")


class GeneratedText(Base):
    __tablename__ = "generated_texts"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    type: Mapped[TextType] = mapped_column(Enum(TextType))
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    # Added in Etapa 5 (nullable, so add_missing_columns can add them to an existing database)
    format: Mapped[TextFormat | None] = mapped_column(Enum(TextFormat), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # verification result
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="generated_texts")


class LeadStatus(str, enum.Enum):
    NEW = "new"              # nova: veio de um e-mail de alerta, ainda não vista
    IMPORTED = "imported"    # importada: a vaga foi enviada pela extensão do navegador
    DISMISSED = "dismissed"  # descartada


class AlertEmail(Base):
    """A job alert email already read, so it is never read (and paid for) twice."""

    __tablename__ = "alert_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(500), unique=True)
    sender: Mapped[str] = mapped_column(String(300), default="")
    subject: Mapped[str] = mapped_column(String(500), default="")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leads_found: Mapped[int] = mapped_column(Integer, default=0)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobLead(Base):
    """A posting announced in a job alert email: only title, company, location and link.
    The full text comes later, when the user opens the link and sends the page with the extension."""

    __tablename__ = "job_leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True)  # canonical_job_url
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(200), default="")  # sender domain, e.g. "linkedin.com"
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.NEW)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # no FK: the job may be deleted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
