"""One check of the job alert emails: read the new ones, save their postings as leads.

An email is recorded only after it was read successfully, so a failure is retried next time.
A lead whose posting is already on the board is saved as "imported" (it is not shown as new).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts.mailbox import AlertMessage
from app.alerts.reader import read_alert
from app.llm.client import LLMClient, LLMOutputError
from app.models import AlertEmail, Job, JobLead, LeadStatus

logger = logging.getLogger(__name__)

FetchAlerts = Callable[[Callable[[str], bool]], list[AlertMessage]]  # (is_known) -> new emails


@dataclass
class CheckResult:
    emails_read: int = 0
    leads_new: int = 0
    leads_known: int = 0     # already listed by an earlier email
    errors: list[str] = field(default_factory=list)


def check_alerts(db: Session, llm: LLMClient, fetch: FetchAlerts) -> CheckResult:
    """Raises MailboxError if the mailbox can't be read at all."""
    known_ids = set(db.scalars(select(AlertEmail.message_id)))
    messages = fetch(lambda message_id: message_id in known_ids)
    result = CheckResult()
    leads_by_url = {lead.url: lead for lead in db.scalars(select(JobLead))}
    jobs_by_url = {url: job_id for job_id, url in db.execute(select(Job.id, Job.url)) if url}

    for message in messages:
        try:
            leads = read_alert(llm, message)
        except (LLMOutputError, anthropic.APIError) as exc:
            message_text = getattr(exc, "message", None) or str(exc)
            result.errors.append(f"{message.subject or message.sender}: {message_text}")
            logger.warning("alerts: could not read %s: %s", message.message_id, message_text)
            continue
        for lead in leads:
            if lead.url in leads_by_url:
                result.leads_known += 1
                continue
            job_id = jobs_by_url.get(lead.url)
            row = JobLead(
                url=lead.url, title=lead.title[:300], company=lead.company[:200], location=lead.location[:200],
                source=message.sender_domain, received_at=message.received_at, job_id=job_id,
                status=LeadStatus.IMPORTED if job_id else LeadStatus.NEW,
            )
            db.add(row)
            leads_by_url[lead.url] = row
            result.leads_new += 1
        db.add(AlertEmail(
            message_id=message.message_id[:500], sender=message.sender[:300], subject=message.subject[:500],
            received_at=message.received_at, leads_found=len(leads),
        ))
        db.commit()
        result.emails_read += 1
    return result
