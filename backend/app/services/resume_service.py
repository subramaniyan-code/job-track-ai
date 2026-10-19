import io
import json
import logging
import re
from typing import Any, Optional

import httpx
from pypdf import PdfReader

from ..config import settings

log = logging.getLogger("resume_service")

RESUME_PARSE_PROMPT = """You are an expert technical recruiter analyzing a job seeker's resume to configure an automated job search on Naukri and other portals.

Extract structured information from the resume text. Return ONLY a valid JSON object matching exactly this schema (no markdown formatting, no code fences):
{{
  "full_name": "<candidate name or null>",
  "email": "<candidate email or null>",
  "phone": "<candidate phone or null>",
  "primary_roles": ["<Role 1, e.g. Full Stack Developer>", "<Role 2, e.g. Backend Developer>"],
  "skills": ["<Skill 1>", "<Skill 2>", "<Skill 3>"],
  "experience_years": <number of total years of experience, e.g. 3.5, or 0.0 if fresher>,
  "preferred_locations": ["<City 1, e.g. Bengaluru>", "<City 2, e.g. Hyderabad>", "Remote"],
  "naukri_search_queries": ["<Query 1, e.g. Python Developer>", "<Query 2, e.g. Full Stack Engineer>"],
  "summary": "<2-sentence executive summary of candidate strengths>"
}}

Rules:
- "primary_roles": top 2-3 standard industry job titles matching candidate experience.
- "skills": top 8-15 core technical skills, frameworks, and tools.
- "naukri_search_queries": 2-4 clean search phrases optimized for Indian job portals like Naukri.com.
- "experience_years": estimate realistically from work dates, default to 0 for freshers.

Resume text:
{resume_text}
"""

COMMON_SKILLS = [
    "python", "javascript", "typescript", "react", "next.js", "node.js", "fastapi",
    "django", "flask", "java", "spring boot", "c++", "c#", ".net", "sql", "postgresql",
    "mysql", "mongodb", "redis", "docker", "kubernetes", "aws", "azure", "gcp",
    "git", "ci/cd", "rest api", "graphql", "html", "css", "tailwind", "linux",
    "data science", "machine learning", "pandas", "numpy", "tensorflow", "pytorch"
]

INDIAN_CITIES = [
    "Bengaluru", "Bangalore", "Hyderabad", "Pune", "Mumbai", "Chennai",
    "Delhi", "Noida", "Gurugram", "Gurgaon", "Kolkata", "Remote"
]


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts raw text from an uploaded PDF resume."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                text_parts.append(txt)
        return "\n".join(text_parts).strip()
    except Exception as e:
        log.error("Failed to extract text from PDF: %s", e)
        raise ValueError("Could not read the uploaded PDF file. Please ensure it is a valid document.")


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _heuristic_resume_parse(text: str) -> dict[str, Any]:
    """Fallback rule-based resume parsing when Gemini is unavailable."""
    text_lower = text.lower()

    # Extract email
    m_email = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)
    email = m_email.group(0) if m_email else None

    # Extract phone
    m_phone = re.search(r"(?:(?:\+91|91|0)?[ -]?)?([6-9]\d{9}|\b\d{3}[- ]?\d{3}[- ]?\d{4}\b)", text)
    phone = m_phone.group(0).strip() if m_phone else None

    # Extract matched skills
    matched_skills = [s.title() for s in COMMON_SKILLS if s in text_lower]

    # Extract locations
    locations = [c for c in INDIAN_CITIES if c.lower() in text_lower]
    if not locations:
        locations = ["Bengaluru", "Remote"]

    # Deduce experience years roughly
    years_found = [int(y) for y in re.findall(r"\b(20[0-2][0-9])\b", text)]
    exp_years = 0.0
    if len(years_found) >= 2:
        exp_years = min(15.0, max(0.0, float(max(years_found) - min(years_found))))

    # Default roles based on skills
    roles = []
    if any(k in text_lower for k in ["react", "next", "frontend", "html"]):
        roles.append("Frontend Developer")
    if any(k in text_lower for k in ["python", "fastapi", "django", "node", "backend"]):
        roles.append("Backend Developer")
    if "Frontend Developer" in roles and "Backend Developer" in roles:
        roles.insert(0, "Full Stack Developer")
    if not roles:
        roles = ["Software Engineer", "Developer"]

    queries = [f"{r} {locations[0]}" for r in roles[:2]]

    return {
        "full_name": None,
        "email": email,
        "phone": phone,
        "primary_roles": roles[:3],
        "skills": matched_skills[:12],
        "experience_years": round(exp_years, 1),
        "preferred_locations": locations[:3],
        "naukri_search_queries": queries,
        "summary": f"Software professional with skills in {', '.join(matched_skills[:5])}.",
    }


async def parse_resume_with_ai(resume_text: str) -> dict[str, Any]:
    """Sends resume text to Gemini AI to extract structured candidate details."""
    if not settings.google_ai_api_key:
        log.info("No GOOGLE_AI_API_KEY configured; using heuristic resume extraction.")
        return _heuristic_resume_parse(resume_text)

    prompt = RESUME_PARSE_PROMPT.format(resume_text=resume_text[:6000])
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.google_ai_model}:generateContent?key={settings.google_ai_api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1000},
    }

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(_strip_code_fences(text))
        return {
            "full_name": parsed.get("full_name"),
            "email": parsed.get("email"),
            "phone": parsed.get("phone"),
            "primary_roles": parsed.get("primary_roles") or ["Software Developer"],
            "skills": parsed.get("skills") or [],
            "experience_years": float(parsed.get("experience_years") or 0.0),
            "preferred_locations": parsed.get("preferred_locations") or ["Bengaluru", "Remote"],
            "naukri_search_queries": parsed.get("naukri_search_queries") or ["Software Engineer"],
            "summary": parsed.get("summary") or "Parsed profile",
        }
    except Exception as e:
        log.warning("Gemini resume analysis failed (%s); falling back to heuristic parsing", e)
        return _heuristic_resume_parse(resume_text)
