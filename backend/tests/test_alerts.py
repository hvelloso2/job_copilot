"""Job alert emails, leads and the browser extension import. IMAP and Claude are mocked."""

import imaplib
import json
from datetime import datetime, timezone
from email.message import EmailMessage

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.alerts.mailbox import AlertMessage, MailboxError, fetch_alerts, parse_message
from app.alerts.reader import alert_text, read_alert
from app.alerts.runner import check_alerts
from app.config import get_settings
from app.database import get_db
from app.dependencies import get_llm_client
from app.job_urls import canonical_job_url
from app.main import app
from app.models import AlertEmail, Job, JobLead, LeadStatus
from app.routers import alerts as alerts_router
from tests.helpers import fake_llm, fake_response, make_settings

EXTRACTION = json.dumps({"tracks": [{
    "company": "Acme", "title": "Dev Python", "seniority": None, "work_mode": None, "location": None,
    "required_requirements": ["Python"], "preferred_requirements": [], "technologies": ["Python"],
    "responsibilities": [], "benefits": [], "salary": None,
}]})

ALERT_HTML = """<html><head><style>.x{color:red}</style></head><body>
<p>Novas vagas para "desenvolvedor júnior"</p>
<table><tr><td><a href="https://www.linkedin.com/comm/jobs/view/111/?trackingId=abc&refId=x">Desenvolvedor Python Júnior</a></td></tr>
<tr><td>Acme · São Paulo (remoto)</td></tr>
<tr><td><a href="https://www.linkedin.com/comm/jobs/view/222/?trackingId=def">Back-end Developer</a></td></tr>
<tr><td>Beta</td></tr></table>
<a href="https://www.linkedin.com/comm/jobs/search?keywords=dev">Ver todas as vagas</a>
<a href="https://www.linkedin.com/comm/jobs/view/111/?trackingId=zzz">Candidatar-se</a>
</body></html>"""


def alert(message_id: str = "<1@linkedin.com>", html: str = ALERT_HTML, day: int = 18) -> AlertMessage:
    return AlertMessage(
        message_id=message_id, sender="jobalerts-noreply@linkedin.com", subject="Vagas para você",
        received_at=datetime(2026, 11, day, 10, tzinfo=timezone.utc), html=html, text="",
    )


def found(*postings) -> str:
    return json.dumps({"postings": [
        {"link": link, "title": title, "company": company, "location": location}
        for link, title, company, location in postings
    ]})


TWO_POSTINGS = found((0, "Desenvolvedor Python Júnior", "Acme", "São Paulo (remoto)"), (1, "Back-end Developer", "Beta", None))


# --- addresses ---


@pytest.mark.parametrize("url, expected", [
    ("https://www.linkedin.com/comm/jobs/view/4123/?trackingId=a&refId=b", "https://www.linkedin.com/jobs/view/4123/"),
    ("https://br.linkedin.com/jobs/view/dev-python-at-acme-4123?trk=x", "https://www.linkedin.com/jobs/view/4123/"),
    ("https://www.linkedin.com/jobs/search/?currentJobId=4123&keywords=dev", "https://www.linkedin.com/jobs/view/4123/"),
    ("https://br.indeed.com/viewjob?jk=abc123&utm_source=alert&from=x", "https://br.indeed.com/viewjob?jk=abc123&from=x"),
    ("https://Acme.gupy.io/jobs/99?jobBoardSource=gupy_public_page#apply", "https://acme.gupy.io/jobs/99"),
])
def test_canonical_job_url(url, expected) -> None:
    assert canonical_job_url(url) == expected


# --- reading an email ---


def test_parse_message_reads_headers_and_html() -> None:
    msg = EmailMessage()
    msg["From"] = "LinkedIn Vagas <jobalerts-noreply@linkedin.com>"
    msg["Subject"] = "Desenvolvedor: 2 vagas novas"
    msg["Message-ID"] = "<abc@linkedin.com>"
    msg["Date"] = "Wed, 18 Nov 2026 10:00:00 -0300"
    msg.set_content("versão texto")
    msg.add_alternative("<p>versão html</p>", subtype="html")

    parsed = parse_message(msg.as_bytes())

    assert (parsed.message_id, parsed.sender, parsed.sender_domain) == ("<abc@linkedin.com>", "jobalerts-noreply@linkedin.com", "linkedin.com")
    assert parsed.received_at == datetime(2026, 11, 18, 13, tzinfo=timezone.utc)
    assert "versão html" in parsed.html and "versão texto" in parsed.text


def test_alert_text_numbers_each_link_once() -> None:
    text, links = alert_text(alert())
    assert "Desenvolvedor Python Júnior [0]" in text and "Back-end Developer [1]" in text
    assert "Candidatar-se [3]" in text and "color:red" not in text
    assert len(links) == 4  # the same address with another trackingId is another link, deduped later


def test_plain_text_email_numbers_the_addresses() -> None:
    message = alert(html="")
    message.text = "Dev Python - Acme\nhttps://br.indeed.com/viewjob?jk=1\n"
    text, links = alert_text(message)
    assert "https://br.indeed.com/viewjob?jk=1" not in text and "[0]" in text
    assert links == ["https://br.indeed.com/viewjob?jk=1"]


def test_read_alert_keeps_only_what_is_written_in_the_email() -> None:
    llm = fake_llm(fake_response(found(
        (0, "Desenvolvedor Python Júnior", "Acme", "São Paulo (remoto)"),
        (1, "Back-end Developer", "Empresa Inventada", "Recife"),  # company/location not in the email
        (2, "Engenheiro de Dados Sênior", None, None),               # title not in the email
        (9, "Back-end Developer", None, None),                        # link number that does not exist
        (3, "Desenvolvedor Python Júnior", "Acme", None),            # same posting, other link
    )))

    leads = read_alert(llm, alert())

    assert [(l.url, l.title, l.company, l.location) for l in leads] == [
        ("https://www.linkedin.com/jobs/view/111/", "Desenvolvedor Python Júnior", "Acme", "São Paulo (remoto)"),
        ("https://www.linkedin.com/jobs/view/222/", "Back-end Developer", "", ""),
    ]
    prompt = llm.sdk.messages.create.call_args.kwargs["messages"][0]["content"]
    assert prompt.startswith("De: jobalerts-noreply@linkedin.com\nAssunto: Vagas para você")
    assert [c.operation for c in llm.calls] == ["read_job_alert"]


def test_email_without_links_does_not_call_claude() -> None:
    llm = fake_llm()
    assert read_alert(llm, alert(html="<p>Seu resumo semanal</p>")) == [] and llm.calls == []


# --- IMAP ---


def raw_email(message_id: str, sender: str = "jobalerts-noreply@linkedin.com") -> bytes:
    msg = EmailMessage()
    msg["From"], msg["Subject"], msg["Message-ID"] = sender, "Vagas", message_id
    msg.set_content("<a href='https://x.com/1'>Dev</a>", subtype="html")
    return msg.as_bytes()


class FakeImap:
    def __init__(self, emails: dict[bytes, bytes], fail_login: bool = False) -> None:
        self.emails, self.fail_login, self.commands, self.logged_out = emails, fail_login, [], False

    def login(self, user, password):
        if self.fail_login:
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials")

    def select(self, folder, readonly=False):
        self.commands.append(("SELECT", folder, readonly))
        return "OK", [b"3"]

    def uid(self, command, *args):
        self.commands.append((command, *args))
        if command == "SEARCH":
            return "OK", [b" ".join(self.emails)] if args[-1] == '"linkedin.com"' else [b""]
        return "OK", [(b"1 (BODY[] {10}", self.emails[args[0]]), b")"]

    def logout(self):
        self.logged_out = True


def test_fetch_alerts_reads_new_emails_newest_first_without_marking_them() -> None:
    emails = {b"1": raw_email("<old@x>"), b"2": raw_email("<known@x>"), b"3": raw_email("<new@x>"),
              b"4": raw_email("<spoof@x>", sender="linkedin.com.fake@golpe.com")}
    imap = FakeImap(emails)
    settings = make_settings(imap_user="eu@gmail.com", imap_password="senha-de-app", alert_senders="linkedin.com,gupy.io")

    messages = fetch_alerts(settings, lambda mid: mid == "<known@x>", connect=lambda host: imap)

    assert [m.message_id for m in messages] == ["<new@x>", "<old@x>"]
    assert ("SELECT", "INBOX", True) in imap.commands
    search = next(c for c in imap.commands if c[0] == "SEARCH")
    assert search[2] == "SINCE" and len(search[3].split("-")) == 3 and search[4:] == ("FROM", '"linkedin.com"')
    assert all(c[2] == "(BODY.PEEK[])" for c in imap.commands if c[0] == "FETCH")
    assert imap.logged_out


def test_fetch_alerts_respects_the_limit_and_reports_a_bad_login() -> None:
    emails = {str(i).encode(): raw_email(f"<{i}@x>") for i in range(1, 6)}
    settings = make_settings(imap_user="eu", imap_password="p", alert_max_emails=2)
    assert len(fetch_alerts(settings, lambda mid: False, connect=lambda host: FakeImap(emails))) == 2

    with pytest.raises(MailboxError, match="senha de app"):
        fetch_alerts(settings, lambda mid: False, connect=lambda host: FakeImap({}, fail_login=True))


# --- a check ---


def test_check_saves_leads_once_and_records_the_emails(db) -> None:
    db.add(Job(raw_text="já no quadro", url="https://www.linkedin.com/jobs/view/222/", extracted={"tracks": []}))
    db.commit()
    same_postings_again = found((0, "Desenvolvedor Python Júnior", None, None))
    llm = fake_llm(fake_response(TWO_POSTINGS), fake_response(same_postings_again))

    result = check_alerts(db, llm, lambda is_known: [alert("<1@x>", day=18), alert("<2@x>", day=17)])

    assert (result.emails_read, result.leads_new, result.leads_known) == (2, 2, 1)
    leads = {lead.url: lead for lead in db.scalars(select(JobLead))}
    first = leads["https://www.linkedin.com/jobs/view/111/"]
    assert (first.title, first.company, first.source, first.status) == ("Desenvolvedor Python Júnior", "Acme", "linkedin.com", LeadStatus.NEW)
    assert leads["https://www.linkedin.com/jobs/view/222/"].status == LeadStatus.IMPORTED  # already on the board
    assert sorted(db.scalars(select(AlertEmail.message_id))) == ["<1@x>", "<2@x>"]

    seen = []
    check_alerts(db, fake_llm(), lambda is_known: seen.extend([is_known("<1@x>"), is_known("<3@x>")]) or [])
    assert seen == [True, False]


def test_an_email_that_fails_is_retried_next_time(db) -> None:
    llm = fake_llm(fake_response(stop_reason="max_tokens"), fake_response(TWO_POSTINGS))
    result = check_alerts(db, llm, lambda is_known: [alert("<1@x>"), alert("<2@x>")])
    assert result.emails_read == 1 and len(result.errors) == 1 and result.leads_new == 2
    assert list(db.scalars(select(AlertEmail.message_id))) == ["<2@x>"]


# --- API ---


@pytest.fixture
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def configured(**overrides):
    return lambda: make_settings(imap_user="eu@gmail.com", imap_password="senha-de-app", **overrides)


def test_alerts_need_the_mailbox_configured(api) -> None:
    app.dependency_overrides[get_settings] = lambda: make_settings(imap_user="", imap_password="")
    app.dependency_overrides[get_llm_client] = lambda: fake_llm()
    assert api.get("/alerts").json()["configured"] is False
    assert api.post("/alerts/check").status_code == 409


def test_check_lists_and_dismisses_leads(api) -> None:
    app.dependency_overrides[get_settings] = configured()
    app.dependency_overrides[get_llm_client] = lambda: fake_llm(fake_response(TWO_POSTINGS))
    app.dependency_overrides[alerts_router.get_alert_fetcher] = lambda: (lambda is_known: [alert()])

    checked = api.post("/alerts/check").json()
    assert checked == {"emails_read": 1, "leads_new": 2, "leads_known": 0, "errors": []}
    status = api.get("/alerts").json()
    assert status["mailbox"] == "eu@gmail.com / INBOX" and status["emails_read"] == 1

    leads = api.get("/leads", params={"status": "new"}).json()
    assert [lead["title"] for lead in leads] == ["Desenvolvedor Python Júnior", "Back-end Developer"]
    dismissed = api.patch(f"/leads/{leads[0]['id']}", json={"status": "dismissed"}).json()
    assert dismissed["status"] == "dismissed"
    assert len(api.get("/leads", params={"status": "new"}).json()) == 1
    assert api.patch(f"/leads/{leads[1]['id']}", json={"status": "imported"}).status_code == 422


def test_unreadable_mailbox_is_a_clear_error(api) -> None:
    def broken(is_known):
        raise MailboxError("o servidor recusou o login")

    app.dependency_overrides[get_settings] = configured()
    app.dependency_overrides[get_llm_client] = lambda: fake_llm()
    app.dependency_overrides[alerts_router.get_alert_fetcher] = lambda: broken
    response = api.post("/alerts/check")
    assert response.status_code == 502 and "recusou o login" in response.json()["detail"]


# --- browser extension ---


def test_import_page_extracts_once_and_marks_the_lead(api, db) -> None:
    db.add(JobLead(url="https://www.linkedin.com/jobs/view/4123/", title="Dev Python", source="linkedin.com"))
    db.commit()
    llm = fake_llm(fake_response(EXTRACTION))
    app.dependency_overrides[get_llm_client] = lambda: llm
    page = {"url": "https://www.linkedin.com/jobs/search/?currentJobId=4123&keywords=python",
            "title": "Dev Python | Acme | LinkedIn", "text": "Dev Python\nAcme\nRequisitos: Python"}

    first = api.post("/jobs/import", json=page)
    again = api.post("/jobs/import", json={**page, "url": "https://www.linkedin.com/jobs/view/4123/?trk=x"})

    assert first.status_code == 201 and first.json()["created"] is True
    assert again.status_code == 200 and again.json() == {"job_id": first.json()["job_id"], "created": False}
    assert len(llm.calls) == 1  # the second time nothing is extracted
    job = db.get(Job, first.json()["job_id"])
    assert job.url == "https://www.linkedin.com/jobs/view/4123/" and job.title == "Dev Python"
    prompt = llm.sdk.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Título da página: Dev Python | Acme | LinkedIn\nEndereço: https://www.linkedin.com/jobs/view/4123/" in prompt
    lead = db.scalar(select(JobLead))
    assert (lead.status, lead.job_id) == (LeadStatus.IMPORTED, job.id)


def test_import_page_rejects_an_empty_page(api) -> None:
    app.dependency_overrides[get_llm_client] = lambda: fake_llm()
    assert api.post("/jobs/import", json={"url": "https://x.com/1", "title": "", "text": ""}).status_code == 422
