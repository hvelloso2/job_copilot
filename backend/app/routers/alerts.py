"""Job alert emails: read the mailbox on demand and list the postings they announce ("leads").

A check reads at most ALERT_MAX_EMAILS new emails (one Claude call each), so it runs in the request.
"""

from functools import partial

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.alerts.mailbox import MailboxError, fetch_alerts
from app.alerts.runner import FetchAlerts, check_alerts
from app.config import Settings, get_settings
from app.database import get_db
from app.dependencies import get_llm_client
from app.llm.client import LLMClient
from app.models import AlertEmail, JobLead, LeadStatus
from app.schemas import AlertCheckOut, AlertsStatus, LeadOut, LeadUpdate

router = APIRouter(tags=["alerts"])


def get_alert_fetcher(settings: Settings = Depends(get_settings)) -> FetchAlerts:
    return partial(fetch_alerts, settings)


@router.get("/alerts", response_model=AlertsStatus)
def alerts_status(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> AlertsStatus:
    """Whether the mailbox is configured (.env) and how many alert emails were read."""
    count, last = db.execute(select(func.count(AlertEmail.id), func.max(AlertEmail.read_at))).one()
    return AlertsStatus(
        configured=settings.imap_configured,
        mailbox=f"{settings.imap_user} / {settings.imap_folder}" if settings.imap_configured else "",
        senders=settings.alert_sender_list(),
        days=settings.alert_days,
        emails_read=count,
        last_read_at=last,
    )


@router.post("/alerts/check", response_model=AlertCheckOut)
def check(
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
    settings: Settings = Depends(get_settings),
    fetch: FetchAlerts = Depends(get_alert_fetcher),
) -> AlertCheckOut:
    """Reads the new job alert emails and saves the postings they announce."""
    if not settings.imap_configured:
        raise HTTPException(status_code=409, detail="Configure IMAP_USER e IMAP_PASSWORD no backend/.env.")
    try:
        result = check_alerts(db, llm, fetch)
    except MailboxError as exc:
        raise HTTPException(status_code=502, detail=f"Não foi possível ler o e-mail: {exc}") from exc
    return AlertCheckOut(**result.__dict__)


@router.get("/leads", response_model=list[LeadOut])
def list_leads(status: LeadStatus | None = None, db: Session = Depends(get_db)) -> list[JobLead]:
    """Postings announced by alert emails: newest email first, in the order of the email."""
    query = select(JobLead)
    if status is not None:
        query = query.where(JobLead.status == status)
    return list(db.scalars(query.order_by(JobLead.received_at.desc().nulls_last(), JobLead.id)))


@router.patch("/leads/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: int, payload: LeadUpdate, db: Session = Depends(get_db)) -> JobLead:
    """Dismisses a lead (or brings it back)."""
    lead = db.get(JobLead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Vaga do alerta não encontrada.")
    lead.status = payload.status
    db.commit()
    return lead
