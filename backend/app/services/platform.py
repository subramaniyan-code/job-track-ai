"""
Infers a human-readable "platform" label (Naukri, LinkedIn, Indeed, etc.)
from a job posting URL or an email sender address, so the dashboard can show
a per-platform breakdown even though these platforms aren't connected via
any API (see README for why — no public API exists for most of them).
"""
import re
from typing import Optional
from urllib.parse import urlparse

_DOMAIN_TO_PLATFORM = {
    "naukri.com": "Naukri",
    "linkedin.com": "LinkedIn",
    "indeed.com": "Indeed",
    "in.indeed.com": "Indeed",
    "shine.com": "Shine",
    "foundit.in": "Foundit",
    "monsterindia.com": "Monster India",
    "monster.com": "Monster",
    "glassdoor.com": "Glassdoor",
    "adzuna.in": "Adzuna",
    "adzuna.com": "Adzuna",
    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "workday.com": "Workday",
    "myworkdayjobs.com": "Workday",
    "smartrecruiters.com": "SmartRecruiters",
    "icims.com": "iCIMS",
    "ashbyhq.com": "Ashby",
}


def _registrable_domain(host: str) -> str:
    """Rough last-two-labels extraction — good enough for the known list
    above without pulling in a full public-suffix-list dependency."""
    parts = host.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def infer_platform(url: Optional[str] = None, email_address: Optional[str] = None) -> str:
    host = None
    if url:
        try:
            host = urlparse(url).netloc
        except Exception:
            host = None
    if not host and email_address:
        match = re.search(r"@([\w.-]+)", email_address)
        if match:
            host = match.group(1)

    if not host:
        return "Other"

    domain = _registrable_domain(host)
    return _DOMAIN_TO_PLATFORM.get(domain, "Company site" if url else "Other")
