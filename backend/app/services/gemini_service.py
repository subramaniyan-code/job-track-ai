"""
Classifies a job-related email using Google's Gemini API via plain REST
(httpx), not the google-generativeai SDK — keeps the image light, which
matters on a small server.

Get a free key at https://aistudio.google.com/apikey
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

from ..config import settings

CLASSIFY_PROMPT = """You are analyzing one email from a job seeker's inbox to help them track their job search.

Classify it and extract structured info. Respond with ONLY a JSON object (no markdown fences, no other text), matching exactly this shape:
{{
  "type": "application_confirmation" | "interview_invite" | "rejection" | "offer" | "job_alert" | "other",
  "company": "<company name or null>",
  "job_title": "<job title this email is about, or null>",
  "recruiter_email": "<direct recruiter / HR email if found in signature or text, else null>",
  "recruiter_phone": "<recruiter or hiring phone / mobile / WhatsApp number if found in signature or text, else null>",
  "summary": "<one short plain-sentence summary for a dashboard, max 20 words>",
  "extracted_jobs": [{{"title": "...", "company": "...", "url": "..."}}]
}}

Rules:
- "extracted_jobs" should only be non-empty when type is "job_alert" (a digest listing multiple open postings) — extract each posting you can find with a title, company and URL if present in the email body.
- For all other types, "extracted_jobs" should be an empty array.
- If this email isn't actually job-search related at all, use type "other" and leave company/job_title null and extracted_jobs empty.
- Never invent a URL — only include one if it's actually present in the email text.
- If a recruiter signature mentions their direct contact email or phone number, extract it cleanly.

Email from: {from_address}
Email subject: {subject}
Email body:
{body}
"""


@dataclass
class EmailClassification:
    type: str = "other"
    company: Optional[str] = None
    job_title: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_phone: Optional[str] = None
    summary: Optional[str] = None
    extracted_jobs: list[dict] = field(default_factory=list)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _heuristic_classify(from_address: str, subject: str, body: str) -> EmailClassification:
    text = f"{subject} {body[:600]}".lower()
    from_lower = (from_address or "").lower()

    if any(k in text for k in ["interview", "screening", "assessment", "round", "technical discussion", "invitation"]):
        etype = "interview_invite"
    elif any(k in text for k in ["regret", "unfortunately", "not moving forward", "other candidates", "unsuccessful", "position has been filled"]):
        etype = "rejection"
    elif any(k in text for k in ["offer letter", "job offer", "pleased to offer"]):
        etype = "offer"
    elif any(k in text for k in ["job alert", "recommended jobs", "matching jobs", "jobs for you", "vacancies", "open positions"]):
        etype = "job_alert"
    else:
        etype = "application_confirmation"

    company = None
    m = re.search(r"\bat\s+([A-Za-z0-9&.\- ]{2,30})", subject, re.IGNORECASE)
    if m:
        company = m.group(1).strip()
    elif "naukri" in from_lower:
        company = "Naukri"
    elif "linkedin" in from_lower:
        company = "LinkedIn"
    elif "indeed" in from_lower:
        company = "Indeed"
    elif "@" in from_address:
        domain = from_address.split("@")[-1].split(">")[0].strip().lower()
        parts = domain.split(".")
        if len(parts) >= 2 and parts[-2] not in ["gmail", "yahoo", "outlook", "hotmail"]:
            company = parts[-2].capitalize()

    job_title = None
    m_title = re.search(r"(?:for|role|position|as)\s+([A-Za-z0-9/.\- ]{2,40})", subject, re.IGNORECASE)
    if m_title:
        job_title = m_title.group(1).strip()

    # Recruiter contact extraction
    recruiter_email = None
    m_email = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", body)
    if m_email:
        found_em = m_email.group(0).lower()
        if not any(x in found_em for x in ["noreply", "no-reply", "notification", "alert", "mailer", "donotreply", "support"]):
            recruiter_email = found_em
    if not recruiter_email and "@" in from_address:
        if not any(x in from_lower for x in ["noreply", "no-reply", "notification", "alert", "mailer", "donotreply"]):
            m_from = re.search(r"<([^>]+)>", from_address)
            recruiter_email = m_from.group(1).strip() if m_from else from_address.strip()

    recruiter_phone = None
    m_phone = re.search(r"(?:(?:\+91|91|0)?[ -]?)?([6-9]\d{9}|\b\d{3}[- ]?\d{3}[- ]?\d{4}\b)", body)
    if m_phone:
        recruiter_phone = m_phone.group(0).strip()

    summary = (subject[:80] + "...") if len(subject) > 80 else (subject or "Job application update")

    return EmailClassification(
        type=etype,
        company=company,
        job_title=job_title,
        recruiter_email=recruiter_email,
        recruiter_phone=recruiter_phone,
        summary=summary,
        extracted_jobs=[],
    )


async def classify_email(from_address: str, subject: str, body: str) -> Optional[EmailClassification]:
    """Classifies an email using Gemini REST API, or seamlessly falls back to rule-based heuristics."""
    if not settings.google_ai_api_key:
        return _heuristic_classify(from_address, subject, body)

    prompt = CLASSIFY_PROMPT.format(from_address=from_address, subject=subject, body=body[:3000])
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.google_ai_model}:generateContent?key={settings.google_ai_api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500},
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(_strip_code_fences(text))

        return EmailClassification(
            type=parsed.get("type", "other"),
            company=parsed.get("company"),
            job_title=parsed.get("job_title"),
            recruiter_email=parsed.get("recruiter_email"),
            recruiter_phone=parsed.get("recruiter_phone"),
            summary=parsed.get("summary"),
            extracted_jobs=parsed.get("extracted_jobs") or [],
        )
    except Exception:
        return _heuristic_classify(from_address, subject, body)

