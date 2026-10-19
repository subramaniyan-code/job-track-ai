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

Extract structured information from the resume text. Return ONLY a valid JSON object matching exactly this schema:
{{
  "full_name": "<candidate legal full name from header or top of resume>",
  "email": "<candidate primary email>",
  "phone": "<candidate phone number with country code, e.g. +91 88258 39860>",
  "primary_roles": ["<Role 1, e.g. Cloud & Infrastructure Engineer>", "<Role 2, e.g. Azure Administrator>", "<Role 3, e.g. DevOps Engineer>"],
  "skills": ["<Skill 1>", "<Skill 2>", "<Skill 3>"],
  "experience_years": <number of progressive professional work experience years, e.g. 4.0. DO NOT count college or diploma years if they started before work experience>,
  "preferred_locations": ["<City 1, e.g. Chennai>", "<City 2, e.g. Bengaluru>", "Remote"],
  "naukri_search_queries": ["<Query 1, e.g. Cloud Infrastructure Engineer>", "<Query 2, e.g. Azure Administrator>", "<Query 3, e.g. DevOps Engineer Chennai>"],
  "summary": "<2-sentence executive summary emphasizing certifications, core technical domains, and key achievements>"
}}

Guidelines:
- "full_name": Extract the candidate's actual name usually displayed at the top.
- "phone": Preserve the full mobile number with country code if available.
- "primary_roles": 2-4 standard industry titles accurately reflecting candidate's specialization (e.g. Cloud Engineer, DevOps, Azure Administrator, SRE).
- "skills": 15-25 technical skills from cloud platforms, infrastructure as code, CI/CD, containers, monitoring, networking, databases, OS, and automation.
- "experience_years": Accurately identify their progressive professional work experience. If summary states "4+ years of progressive experience", use 4.0.
- "preferred_locations": The candidate's current city and key tech hubs.
- "naukri_search_queries": 3-5 high-value search queries optimized for Indian job recruiters on Naukri.com.

Resume text:
{resume_text}
"""

EXTENSIVE_SKILLS = [
    # Cloud & Virtualization
    "Azure", "Microsoft Azure", "Multi-Cloud", "AWS", "Amazon Web Services", "GCP", "Google Cloud",
    "OVH", "Rackgenius", "Virtual Machines", "VNet", "Storage Accounts", "App Services", "Entra ID",
    "Azure Cloud Shell", "Azure Automation", "Cost Optimization", "FinOps", "CSP", "CSP Billing",
    # Infrastructure as Code & Automation
    "ARM Templates", "Terraform", "PowerShell", "Bash", "Shell Scripting", "Python", "Google Apps Script",
    "Ansible", "Puppet", "Chef", "CloudFormation",
    # Containers & CI/CD
    "Docker", "Kubernetes", "AKS", "Azure Kubernetes Service", "GitHub Actions", "Azure DevOps",
    "CI/CD", "CI/CD Pipelines", "GitHub Self-Hosted Runners", "Git", "GitLab CI", "Jenkins", "Helm",
    # Monitoring & Observability
    "Azure Monitor", "Prometheus", "Grafana", "Node Exporter", "Sentry", "PagerDuty", "Datadog",
    "ELK", "Log Analysis", "Alerting", "Incident Management",
    # Networking & Security
    "Tailscale", "Headscale", "Private Networking", "VNet Peering", "NAT Gateway", "DNS", "Load Balancing",
    "Sophos", "Sophos XGS Firewall", "SSL VPN", "VPN", "IAM", "RBAC", "Azure AD", "Zoho Vault",
    "Zero Trust", "Zero Public Exposure", "Security Audits", "Compliance",
    # OS & Systems
    "Linux", "Ubuntu Linux", "Linux Server Administration", "Windows Server", "VM Patching", "CentOS",
    "RedHat", "Debian",
    # Databases & Caching
    "MongoDB", "PostgreSQL", "Azure Cosmos DB", "MySQL", "Redis", "RabbitMQ", "SQL", "Database Migration",
    "Backup and Recovery",
    # Web & Application Servers
    "Nginx", "PM2", "Apache", "REST API", "Microservices",
    # Email Infrastructure & Admin
    "MailWizz", "Stalwart", "SPF", "DKIM", "DMARC", "MX Records", "Google Workspace", "Microsoft 365",
    "Zoho Creator", "IT Asset Management"
]

ROLE_DEFINITIONS = [
    {
        "role": "Cloud & Infrastructure Engineer",
        "keywords": ["cloud & infrastructure", "infrastructure engineer", "cloud infrastructure", "azure", "multi-cloud"],
    },
    {
        "role": "Azure Cloud Administrator",
        "keywords": ["azure administrator", "az-104", "azure", "entra id", "azure monitor", "arm templates"],
    },
    {
        "role": "DevOps Engineer",
        "keywords": ["devops", "ci/cd", "github actions", "docker", "kubernetes", "terraform", "pipeline"],
    },
    {
        "role": "Site Reliability Engineer (SRE)",
        "keywords": ["sre", "site reliability", "prometheus", "grafana", "monitoring", "alerting", "observability"],
    },
    {
        "role": "Linux / Systems Administrator",
        "keywords": ["linux administration", "ubuntu linux", "windows server", "systems administrator", "sysadmin"],
    },
    {
        "role": "Full Stack Developer",
        "keywords": ["full stack", "fullstack", "react", "node", "fastapi", "next.js", "django"],
    },
    {
        "role": "Backend Developer",
        "keywords": ["backend developer", "python developer", "fastapi", "django", "node.js developer"],
    },
    {
        "role": "Data Engineer",
        "keywords": ["data engineer", "data pipeline", "etl", "spark", "hadoop", "snowflake"],
    },
]

INDIAN_CITIES = [
    "Chennai", "Bengaluru", "Bangalore", "Hyderabad", "Pune", "Mumbai",
    "Delhi", "Noida", "Gurugram", "Gurgaon", "Kolkata", "Coimbatore", "Remote"
]


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    """Extracts raw text from an uploaded resume (PDF, DOCX, DOC, or TXT)."""
    fn_lower = filename.lower()
    
    # 1. PDF
    if fn_lower.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            for page in reader.pages:
                txt = page.extract_text()
                if txt:
                    text_parts.append(txt)
            raw = "\n".join(text_parts).strip()
            if raw:
                return raw
        except Exception as e:
            log.warning("PDF extraction failed: %s", e)

    # 2. DOCX
    if fn_lower.endswith(".docx") or file_bytes.startswith(b"PK\x03\x04"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            parts = []
            for p in doc.paragraphs:
                if p.text.strip():
                    parts.append(p.text.strip())
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip() and cell.text.strip() not in parts:
                            parts.append(cell.text.strip())
            raw = "\n".join(parts).strip()
            if raw:
                return raw
        except Exception as e:
            log.warning("DOCX extraction failed: %s", e)

    # 3. Legacy DOC or plain text fallback
    try:
        decoded = file_bytes.decode("utf-8", errors="ignore")
        # Extract printable ASCII/Unicode word runs
        words = re.findall(r"[\x20-\x7E\t\n]{4,}", decoded)
        raw = "\n".join(words).strip()
        if len(raw) > 50:
            return raw
    except Exception:
        pass

    raise ValueError("Could not extract readable text from this document. Please ensure it is a valid PDF, DOCX, or DOC file.")


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _heuristic_resume_parse(text: str) -> dict[str, Any]:
    """
    High-precision heuristic parser for resumes when Gemini is offline.
    Extracts candidate name, phone, email, experience, modern tech roles, and skills.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    text_lower = text.lower()

    # 1. Extract Name (examine first 5 non-empty lines)
    full_name = "Candidate"
    for line in lines[:6]:
        if re.search(r"(curriculum|resume|vitae|page\s+\d+|personal|profile|contact)", line, re.I):
            continue
        # Clean special chars
        clean = re.sub(r"[^A-Za-z\s]", " ", line).strip()
        words = clean.split()
        if 1 <= len(words) <= 4 and 4 <= len(clean) <= 45:
            # Check not title
            if not any(w.lower() in ["engineer", "developer", "summary", "experience", "certified", "skills", "chennai", "india"] for w in words):
                full_name = " ".join(w.capitalize() for w in words)
                break

    # 2. Extract Email
    m_email = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)
    email = m_email.group(0).lower() if m_email else None

    # 3. Extract Phone (Indian and International formats)
    phone = None
    m_phone = re.search(r"(\+?91[\s-]?[6-9]\d{4}[\s-]?\d{5}|\+?91[\s-]?[6-9]\d{9}|[6-9]\d{4}[\s-]?\d{5}|\b[6-9]\d{9}\b)", text)
    if m_phone:
        phone = m_phone.group(0).strip()

    # 4. Extract Experience Years
    exp_years = 0.0
    # First priority: explicit "X+ years of experience" or "X+ years of progressive experience"
    m_exp_explicit = re.search(r"(\d+(?:\.\d+)?)\+?\s*years(?:\s+of)?(?:\s+progressive)?\s+experience", text, re.I)
    if m_exp_explicit:
        exp_years = float(m_exp_explicit.group(1))
    else:
        # Check professional summary for "X+ years"
        m_summary_exp = re.search(r"\b(\d+(?:\.\d+)?)\+?\s*years\b", text[:1200], re.I)
        if m_summary_exp:
            exp_years = float(m_summary_exp.group(1))
        else:
            # Default reasonable estimation
            exp_years = 3.0

    # 5. Extract Roles
    detected_roles = []
    # Check header lines (e.g., line 2 pipe-separated: Cloud & Infrastructure Engineer | Azure (AZ-104)...)
    for line in lines[1:4]:
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            for p in parts:
                if any(k in p.lower() for k in ["engineer", "administrator", "developer", "architect", "lead", "specialist"]):
                    if len(p) <= 40 and p not in detected_roles:
                        detected_roles.append(p)

    # Match predefined role taxonomy
    for r_def in ROLE_DEFINITIONS:
        score = sum(1 for kw in r_def["keywords"] if kw in text_lower)
        if score >= 2 and r_def["role"] not in detected_roles:
            detected_roles.append(r_def["role"])

    if not detected_roles:
        detected_roles = ["Cloud & Infrastructure Engineer", "DevOps Engineer"]

    # 6. Extract Skills
    matched_skills = []
    for skill in EXTENSIVE_SKILLS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            if skill not in matched_skills:
                matched_skills.append(skill)

    # 7. Extract Preferred Locations
    locations = []
    for city in INDIAN_CITIES:
        if city.lower() in text_lower and city not in locations:
            locations.append(city)
    if not locations:
        locations = ["Chennai", "Bengaluru", "Remote"]
    elif "Remote" not in locations:
        locations.append("Remote")

    # 8. Generate Naukri Search Queries
    primary_city = locations[0] if locations else "Chennai"
    queries = []
    for role in detected_roles[:3]:
        # Clean role of credentials like (AZ-104) for query
        clean_role = re.sub(r"\([^)]*\)", "", role).strip()
        queries.append(f"{clean_role}")
        queries.append(f"{clean_role} {primary_city}")

    # Remove duplicates preserving order
    dedup_queries = []
    for q in queries:
        if q and q not in dedup_queries:
            dedup_queries.append(q)

    # 9. Summary
    core_skills_str = ", ".join(matched_skills[:6])
    summary = (
        f"{full_name} is an experienced {detected_roles[0]} with {exp_years} years of professional experience. "
        f"Key expertise includes {core_skills_str}."
    )

    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "primary_roles": detected_roles[:4],
        "skills": matched_skills[:20],
        "experience_years": round(exp_years, 1),
        "preferred_locations": locations[:4],
        "naukri_search_queries": dedup_queries[:4],
        "summary": summary,
        "parser_source": "heuristic",
        "parser_message": "Parsed with High-Precision Heuristic Engine. (To enable Gemini 2.0 Flash AI, add your free API key in Settings).",
    }


async def parse_resume_with_ai(
    resume_text: str,
    custom_gemini_key: Optional[str] = None
) -> dict[str, Any]:
    """
    Sends resume text to Google Gemini AI to extract structured candidate details.
    Uses custom key if provided by user, else falls back to server GOOGLE_AI_API_KEY.
    Gracefully falls back to high-precision heuristic if no key or error occurs.
    """
    api_key = custom_gemini_key or settings.google_ai_api_key
    if not api_key:
        log.info("No Gemini API key available; using high-precision heuristic.")
        return _heuristic_resume_parse(resume_text)

    prompt = RESUME_PARSE_PROMPT.format(resume_text=resume_text[:7000])
    
    # Try models in order: gemini-2.0-flash, then gemini-1.5-flash
    models_to_try = [settings.google_ai_model or "gemini-2.0-flash", "gemini-1.5-flash"]
    last_error = None

    for model_name in models_to_try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1500,
                "responseMimeType": "application/json",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            candidates = data.get("candidates", [])
            if not candidates or "content" not in candidates[0]:
                raise ValueError("Empty response received from Gemini API.")

            raw_text = candidates[0]["content"]["parts"][0]["text"]
            parsed = json.loads(_strip_code_fences(raw_text))

            return {
                "full_name": parsed.get("full_name") or "Candidate",
                "email": parsed.get("email"),
                "phone": parsed.get("phone"),
                "primary_roles": parsed.get("primary_roles") or ["Cloud & Infrastructure Engineer"],
                "skills": parsed.get("skills") or [],
                "experience_years": float(parsed.get("experience_years") or 0.0),
                "preferred_locations": parsed.get("preferred_locations") or ["Chennai", "Remote"],
                "naukri_search_queries": parsed.get("naukri_search_queries") or ["Cloud Infrastructure Engineer"],
                "summary": parsed.get("summary") or "Parsed profile",
                "parser_source": "gemini",
                "parser_message": f"Successfully parsed and synthesized with Google Gemini AI ({model_name}).",
            }
        except Exception as e:
            log.warning("Gemini model '%s' failed: %s", model_name, e)
            last_error = str(e)
            continue

    log.warning("All Gemini models failed (%s); falling back to heuristic parsing", last_error)
    heuristic_res = _heuristic_resume_parse(resume_text)
    heuristic_res["parser_source"] = "heuristic"
    heuristic_res["parser_message"] = (
        f"Gemini API returned an error: {last_error[:100]}. "
        f"Candidate information was parsed using the High-Precision Heuristic Engine."
    )
    return heuristic_res
