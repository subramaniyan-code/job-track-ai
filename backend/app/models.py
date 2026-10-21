import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, Enum, Float, JSON, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    super_admin = "super_admin"
    user = "user"


class ApplicationStatus(str, enum.Enum):
    saved = "saved"
    applied = "applied"
    interviewing = "interviewing"
    offer = "offer"
    rejected = "rejected"
    ghosted = "ghosted"


class FollowUpStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    sent = "sent"
    skipped = "skipped"


class ConnectorProvider(str, enum.Enum):
    adzuna = "adzuna"
    greenhouse = "greenhouse"
    lever = "lever"
    jsearch = "jsearch"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(Role), default=Role.user, nullable=False)
    is_active = Column(Boolean, default=True)
    timezone = Column(String, default="Asia/Kolkata")
    created_at = Column(DateTime, default=datetime.utcnow)

    api_connections = relationship("ApiConnection", back_populates="user", cascade="all, delete-orphan")
    email_account = relationship("EmailAccount", back_populates="user", uselist=False, cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")


class ApiConnection(Base):
    """A user's own credentials for a job-source API (Adzuna, JSearch, etc.)."""
    __tablename__ = "api_connections"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    provider = Column(Enum(ConnectorProvider), nullable=False)
    label = Column(String, nullable=True)
    credentials_encrypted = Column(Text, nullable=False)  # JSON blob, encrypted at rest
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_connections")


class EmailAccount(Base):
    """The SMTP + IMAP account a user connects: SMTP sends follow-ups as them,
    IMAP reads their inbox so job-related replies/alerts can be analyzed."""
    __tablename__ = "email_accounts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), unique=True, nullable=False)

    smtp_host = Column(String, nullable=False)
    smtp_port = Column(Integer, default=587)
    smtp_username = Column(String, nullable=False)
    smtp_password_encrypted = Column(Text, nullable=False)
    from_name = Column(String, nullable=True)

    # IMAP (inbox reading for analysis). Defaults to the SMTP credentials
    # if left blank — most providers (Gmail, Outlook) use the same login
    # for both, just a different host.
    imap_host = Column(String, nullable=True)
    imap_port = Column(Integer, default=993)
    imap_enabled = Column(Boolean, default=False)
    last_seen_uid = Column(String, nullable=True)  # IMAP UID watermark, so each poll only looks at new mail

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="email_account")


class EmailInsightType(str, enum.Enum):
    application_confirmation = "application_confirmation"
    interview_invite = "interview_invite"
    rejection = "rejection"
    offer = "offer"
    job_alert = "job_alert"
    other = "other"


class EmailInsight(Base):
    """One analyzed inbox email: a reply about a tracked application, or a
    job-alert digest that may contain new postings to surface on the dashboard."""
    __tablename__ = "email_insights"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    message_id = Column(String, nullable=False)  # IMAP Message-ID header, used to de-dup
    from_address = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    received_at = Column(DateTime, nullable=True)

    insight_type = Column(Enum(EmailInsightType), default=EmailInsightType.other, nullable=False)
    company = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    platform = Column(String, nullable=True)  # inferred from sender domain — see services/platform.py
    summary = Column(Text, nullable=True)  # one-line human-readable summary for the dashboard
    matched_application_id = Column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=True)
    extracted_jobs = Column(JSON, nullable=True)  # for job_alert emails: [{title, company, url}, ...]

    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    matched_application = relationship("Application")


class Job(Base):
    """A job posting pulled from a connected source. Shared/deduped across users."""
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    source = Column(String, nullable=False)          # adzuna / greenhouse / lever / jsearch / manual
    external_id = Column(String, nullable=False)      # id/url from the source, used for de-dup
    title = Column(String, nullable=False)
    company = Column(String, nullable=True)
    location = Column(String, nullable=True)
    remote = Column(Boolean, default=False)
    url = Column(String, nullable=False)
    platform = Column(String, nullable=True)  # Naukri / LinkedIn / Indeed / Shine / Company site / etc — see services/platform.py
    description = Column(Text, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    raw = Column(JSON, nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_currency = Column(String, default="INR", nullable=True)


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    job_id = Column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.saved, nullable=False)
    fit_score = Column(Float, nullable=True)          # 0-100, from resume/JD matching
    recruiter_email = Column(String, nullable=True)   # who follow-up emails go to
    recruiter_phone = Column(String, nullable=True)   # recruiter contact phone / WhatsApp
    salary_expectation = Column(String, nullable=True)
    resume_version = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    last_activity_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="applications")
    job = relationship("Job")
    followups = relationship("FollowUp", back_populates="application", cascade="all, delete-orphan")
    events = relationship("ApplicationEvent", back_populates="application", cascade="all, delete-orphan", order_by="ApplicationEvent.created_at")


class FollowUp(Base):
    __tablename__ = "followups"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    application_id = Column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    template_used = Column(String, nullable=True)
    status = Column(Enum(FollowUpStatus), default=FollowUpStatus.draft, nullable=False)
    suggested_send_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="followups")


class ApplicationEvent(Base):
    """Audit log entry for an application — status changes, creation, notes, etc."""
    __tablename__ = "application_events"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    application_id = Column(UUID(as_uuid=False), ForeignKey("applications.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    event_type = Column(String, nullable=False)   # e.g. 'created', 'status_change'
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=True)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="events")
    user = relationship("User")


class CandidateProfile(Base):
    """Parsed resume information and career search preferences."""
    __tablename__ = "candidate_profiles"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), unique=True, nullable=False)
    full_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    primary_roles = Column(JSON, nullable=True)         # list of strings: ["Full Stack Developer", "Backend Engineer"]
    skills = Column(JSON, nullable=True)                # list of strings: ["Python", "FastAPI", "React", "Docker"]
    experience_years = Column(Float, default=0.0)
    preferred_locations = Column(JSON, nullable=True)   # list of strings: ["Bengaluru", "Hyderabad", "Remote"]
    naukri_search_queries = Column(JSON, nullable=True) # list of strings: search queries for Naukri
    summary = Column(Text, nullable=True)
    resume_filename = Column(String, nullable=True)
    google_ai_api_key_encrypted = Column(Text, nullable=True)  # Optional per-user Gemini API key
    parser_source = Column(String, default="heuristic")        # 'gemini' or 'heuristic'
    parser_message = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class NaukriBotConfig(Base):
    """Configuration and state for the autonomous stealth Naukri auto-apply worker."""
    __tablename__ = "naukri_bot_configs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), unique=True, nullable=False)
    enabled = Column(Boolean, default=False)
    session_cookies_encrypted = Column(Text, nullable=True)   # JSON string of cookies, encrypted with Fernet
    daily_max_applications = Column(Integer, default=5)       # Strict safety cap per day (5-8 recommended)
    runs_per_day = Column(Integer, default=3)                 # Number of random sessions per day (2-4)
    target_keywords = Column(String, nullable=True)           # e.g. "Python Developer, FastAPI"
    target_locations = Column(String, nullable=True)          # e.g. "Bengaluru, Remote"
    experience_years = Column(Integer, default=0)
    applications_today = Column(Integer, default=0)
    last_reset_date = Column(String, nullable=True)           # "YYYY-MM-DD"
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    status = Column(String, default="idle")                   # idle, running, session_expired, error
    status_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class NaukriBotLog(Base):
    """Audit log entry for Naukri auto-bot actions."""
    __tablename__ = "naukri_bot_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    job_title = Column(String, nullable=False)
    company = Column(String, nullable=True)
    location = Column(String, nullable=True)
    url = Column(String, nullable=True)
    external_apply_url = Column(String, nullable=True)
    key_skills = Column(Text, nullable=True)
    recruiter_email = Column(String, nullable=True)
    recruiter_phone = Column(String, nullable=True)
    action = Column(String, nullable=False)   # 'applied', 'skipped_redirect', 'skipped_questions', 'failed'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
