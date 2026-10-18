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
  "summary": "<one short plain-sentence summary for a dashboard, max 20 words>",
  "extracted_jobs": [{{"title": "...", "company": "...", "url": "..."}}]
}}

Rules:
- "extracted_jobs" should only be non-empty when type is "job_alert" (a digest listing multiple open postings) — extract each posting you can find with a title, company and URL if present in the email body.
- For all other types, "extracted_jobs" should be an empty array.
- If this email isn't actually job-search related at all, use type "other" and leave company/job_title null and extracted_jobs empty.
- Never invent a URL — only include one if it's actually present in the email text.

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
    summary: Optional[str] = None
    extracted_jobs: list[dict] = field(default_factory=list)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def classify_email(from_address: str, subject: str, body: str) -> Optional[EmailClassification]:
    """Returns None (rather than raising) on any API/parse failure — a
    classification miss should never crash the poll loop."""
    if not settings.google_ai_api_key:
        return None

    prompt = CLASSIFY_PROMPT.format(from_address=from_address, subject=subject, body=body)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.google_ai_model}:generateContent?key={settings.google_ai_api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500},
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(_strip_code_fences(text))

        return EmailClassification(
            type=parsed.get("type", "other"),
            company=parsed.get("company"),
            job_title=parsed.get("job_title"),
            summary=parsed.get("summary"),
            extracted_jobs=parsed.get("extracted_jobs") or [],
        )
    except Exception:
        return None
