"""One address per job posting, so the same posting is recognized wherever its link comes from
(a job alert email, the page open in the browser, a search results page)."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_LINKEDIN_JOB = re.compile(r"/jobs/view/(?:[^/?#]*-)?(\d+)")

# Query parameters that only track where the click came from; the rest (e.g. Indeed's "jk") is kept.
_TRACKING = re.compile(
    r"^(utm_.*|trk.*|tracking.*|ref.*|src|source|origin|lipi|midtoken|midsig|eid|otptoken|"
    r"jobboardsource|campaign.*|fbclid|gclid|mc_.*|email.*)$",
    re.IGNORECASE,
)


def canonical_job_url(url: str) -> str:
    """The posting's address without tracking parameters or #fragment.
    LinkedIn links (/comm/jobs/view/123, /jobs/search/?currentJobId=123) become /jobs/view/123/."""
    url = url.strip()
    parts = urlsplit(url)
    if parts.netloc.lower().endswith("linkedin.com"):
        match = _LINKEDIN_JOB.search(parts.path)
        job_id = match.group(1) if match else dict(parse_qsl(parts.query)).get("currentJobId")
        if job_id and job_id.isdigit():
            return f"https://www.linkedin.com/jobs/view/{job_id}/"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING.match(k)]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), ""))
