"""Reads job alert emails over IMAP (read-only: nothing is marked as read, moved or deleted).

Only emails from the configured sender domains and from the last `alert_days` days are read.
"""

import email
import imaplib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime

from app.config import Settings

logger = logging.getLogger(__name__)

MAX_SCANNED = 200  # emails looked at per check (newest first), new or already read
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class MailboxError(Exception):
    """The mailbox can't be read (wrong password, IMAP off, server down)."""


@dataclass
class AlertMessage:
    message_id: str
    sender: str          # email address
    subject: str
    received_at: datetime | None
    html: str
    text: str

    @property
    def sender_domain(self) -> str:
        return self.sender.rpartition("@")[2].lower()


def _imap_date(day: date) -> str:
    """IMAP wants "18-Nov-2026" in English, whatever the system locale is."""
    return f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year}"


def parse_message(raw: bytes) -> AlertMessage:
    message: EmailMessage = email.message_from_bytes(raw, policy=default_policy)  # type: ignore[assignment]
    html_part = message.get_body(preferencelist=("html",))
    text_part = message.get_body(preferencelist=("plain",))
    try:
        received = parsedate_to_datetime(message["Date"]) if message["Date"] else None
    except (TypeError, ValueError):
        received = None
    return AlertMessage(
        message_id=(message["Message-ID"] or "").strip(),
        sender=parseaddr(message["From"] or "")[1].lower(),
        subject=str(message["Subject"] or ""),
        received_at=received,
        html=html_part.get_content() if html_part else "",
        text=text_part.get_content() if text_part else "",
    )


def _from_sender(message: AlertMessage, senders: list[str]) -> bool:
    domain = message.sender_domain
    return any(domain == s or domain.endswith(f".{s}") for s in senders)


def fetch_alerts(
    settings: Settings,
    is_known: Callable[[str], bool],
    connect: Callable[[str], imaplib.IMAP4] = imaplib.IMAP4_SSL,
) -> list[AlertMessage]:
    """New alert emails (not `is_known`), newest first, at most `alert_max_emails`."""
    senders = settings.alert_sender_list()
    since = _imap_date(date.today() - timedelta(days=settings.alert_days))
    try:
        imap = connect(settings.imap_host)
    except OSError as exc:
        raise MailboxError(f"não foi possível conectar a {settings.imap_host}: {exc}") from exc
    try:
        try:
            imap.login(settings.imap_user, settings.imap_password)
        except imaplib.IMAP4.error as exc:
            raise MailboxError(
                "o servidor recusou o login. No Gmail, ative o IMAP e use uma senha de app, não a senha da conta."
            ) from exc
        status, _ = imap.select(settings.imap_folder, readonly=True)
        if status != "OK":
            raise MailboxError(f"a pasta {settings.imap_folder!r} não existe")

        uids: set[bytes] = set()
        for sender in senders:
            status, data = imap.uid("SEARCH", None, "SINCE", since, "FROM", f'"{sender}"')
            if status == "OK" and data and data[0]:
                uids.update(data[0].split())

        found: list[AlertMessage] = []
        for uid in sorted(uids, key=int, reverse=True)[:MAX_SCANNED]:
            status, data = imap.uid("FETCH", uid, "(BODY.PEEK[])")  # PEEK: does not mark as read
            raw = next((part[1] for part in data or [] if isinstance(part, tuple)), None)
            if status != "OK" or raw is None:
                continue
            message = parse_message(raw)
            # IMAP's FROM search matches substrings anywhere in the header: check the real domain
            if not message.message_id or is_known(message.message_id) or not _from_sender(message, senders):
                continue
            found.append(message)
            if len(found) >= settings.alert_max_emails:
                break
        return found
    except imaplib.IMAP4.error as exc:
        raise MailboxError(f"erro do servidor de e-mail: {exc}") from exc
    finally:
        try:
            imap.logout()
        except (imaplib.IMAP4.error, OSError):
            pass
