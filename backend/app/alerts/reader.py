"""Turns a job alert email into job leads (title, company, location, link), with Claude.

The email goes to Claude as text where every link is a number ("Desenvolvedor Python [3]").
Claude answers with link numbers, so every URL comes from the email itself. Title, company and
location are kept only if they are written in the email: nothing about a posting is invented.
"""

import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from app.alerts.mailbox import AlertMessage
from app.job_urls import canonical_job_url
from app.llm.client import LLMClient
from app.llm.prompts import load_prompt
from app.llm.schemas import FoundPostings

MAX_EMAIL_CHARS = 30_000  # long emails are cut, to keep the cost bounded
_BLOCKS = {"p", "div", "br", "li", "tr", "td", "table", "h1", "h2", "h3", "h4", "h5", "h6"}
_HIDDEN = {"script", "style", "head", "title"}
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"')\]]+")


@dataclass
class Lead:
    url: str
    title: str
    company: str
    location: str


class _AlertText(HTMLParser):
    """Email HTML to text, numbering the links: "Desenvolvedor Python [3]"."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.links: list[str] = []
        self._index: dict[str, int] = {}
        self._hrefs: list[str | None] = []
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in _HIDDEN:
            self._hidden += 1
        elif tag == "a":
            self._hrefs.append(dict(attrs).get("href"))
        elif tag in _BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _HIDDEN:
            self._hidden = max(0, self._hidden - 1)
        elif tag == "a" and self._hrefs:
            href = (self._hrefs.pop() or "").strip()
            if href.startswith(("http://", "https://")):
                self.parts.append(f" [{self.number(href)}] ")
        elif tag in _BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.parts.append(data)

    def number(self, href: str) -> int:
        if href not in self._index:
            self._index[href] = len(self.links)
            self.links.append(href)
        return self._index[href]


def _tidy(text: str) -> str:
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def alert_text(message: AlertMessage) -> tuple[str, list[str]]:
    """The email as text with numbered links, and the links (index = number)."""
    parser = _AlertText()
    if message.html.strip():
        parser.feed(message.html)
        parser.close()
        text = "".join(parser.parts)
    else:  # plain-text email: number the addresses written in it
        text = _URL_IN_TEXT.sub(lambda m: f"[{parser.number(m.group(0))}]", message.text)
    return _tidy(text)[:MAX_EMAIL_CHARS], parser.links


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).split())


def _written(value: str | None, folded_email: str) -> str:
    """The value if it is written in the email, else "" (never kept if the model made it up)."""
    value = (value or "").strip()
    return value if value and _fold(value) in folded_email else ""


def read_alert(llm: LLMClient, message: AlertMessage) -> list[Lead]:
    text, links = alert_text(message)
    if not links:
        return []
    found = llm.create_structured(
        "read_job_alert",
        FoundPostings,
        system=load_prompt("read_job_alert"),
        messages=[{"role": "user", "content": f"De: {message.sender}\nAssunto: {message.subject}\n\n{text}"}],
        max_tokens=8000,
    )
    folded = _fold(text)
    leads: dict[str, Lead] = {}
    for item in found.postings:
        title = _written(item.title, folded)
        if not title or not 0 <= item.link < len(links):
            continue  # a title that is not in the email, or a link number that does not exist
        url = canonical_job_url(links[item.link])
        if urlsplit(url).scheme in ("http", "https"):
            leads.setdefault(url, Lead(url=url, title=title, company=_written(item.company, folded),
                                       location=_written(item.location, folded)))
    return list(leads.values())
