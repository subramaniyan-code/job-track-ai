from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr

from .models import Role, ApplicationStatus, FollowUpStatus, ConnectorProvider, EmailInsightType


# ---------- Auth ----------
class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: Role
    is_active: bool
    timezone: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- API Connections ----------
class ApiConnectionCreate(BaseModel):
    provider: ConnectorProvider
    label: Optional[str] = None
    credentials: dict[str, str]  # e.g. {"app_id": "...", "app_key": "..."}


class ApiConnectionOut(BaseModel):
    id: str
    provider: ConnectorProvider
    label: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Email account ----------
class EmailAccountCreate(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: Optional[str] = ""
    from_name: Optional[str] = None
    imap_host: Optional[str] = None  # left blank -> auto-derived from smtp_host where possible
    imap_port: int = 993
    imap_enabled: bool = False


class EmailAccountOut(BaseModel):
    id: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    from_name: Optional[str]
    imap_host: Optional[str]
    imap_port: int
    imap_enabled: bool
    is_active: bool

    class Config:
        from_attributes = True


# ---------- Email insights (inbox analysis) ----------
class EmailInsightOut(BaseModel):
    id: str
    from_address: Optional[str]
    subject: Optional[str]
    received_at: Optional[datetime]
    insight_type: EmailInsightType
    company: Optional[str]
    job_title: Optional[str]
    platform: Optional[str]
    summary: Optional[str]
    matched_application_id: Optional[str]
    extracted_jobs: Optional[list[dict[str, Any]]]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Manual job add ----------
class JobManualCreate(BaseModel):
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    remote: bool = False
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = "INR"


# ---------- Jobs ----------
class JobSearchRequest(BaseModel):
    keywords: str
    location: Optional[str] = None
    remote_only: bool = False
    max_results: int = 30


class JobOut(BaseModel):
    id: str
    source: str
    title: str
    company: Optional[str]
    location: Optional[str]
    remote: bool
    url: str
    platform: Optional[str]
    description: Optional[str]
    posted_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---------- Applications ----------
class ApplicationCreate(BaseModel):
    job_id: str
    status: ApplicationStatus = ApplicationStatus.saved
    resume_version: Optional[str] = None
    notes: Optional[str] = None
    recruiter_email: Optional[str] = None
    salary_expectation: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    resume_version: Optional[str] = None
    notes: Optional[str] = None
    fit_score: Optional[float] = None
    recruiter_email: Optional[str] = None
    salary_expectation: Optional[str] = None


class ApplicationOut(BaseModel):
    id: str
    job: JobOut
    status: ApplicationStatus
    fit_score: Optional[float]
    recruiter_email: Optional[str]
    resume_version: Optional[str]
    salary_expectation: Optional[str]
    notes: Optional[str]
    applied_at: Optional[datetime]
    last_activity_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Application timeline ----------
class ApplicationEventOut(BaseModel):
    id: str
    event_type: str
    from_status: Optional[str]
    to_status: Optional[str]
    note: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True



# ---------- Follow-ups ----------
class FollowUpDraftRequest(BaseModel):
    application_id: str
    template: str = "post_application_checkin"  # or post_interview_thanks / long_silence_nudge
    tone_note: Optional[str] = None  # e.g. "keep it very short"


class FollowUpUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    suggested_send_at: Optional[datetime] = None


class FollowUpOut(BaseModel):
    id: str
    application_id: str
    subject: str
    body: str
    template_used: Optional[str]
    status: FollowUpStatus
    suggested_send_at: Optional[datetime]
    sent_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Dashboard ----------
class DashboardStats(BaseModel):
    total_applications: int
    applied: int
    interviewing: int
    offers: int
    rejected: int
    ghosted: int
    response_rate: float
    pending_followups: int
    applications_last_7_days: int
    applications_last_30_days: int
    unread_inbox_insights: int
    stale_applications: int = 0


class PlatformTrend(BaseModel):
    platform: str
    applied: int
    replies: int  # interview_invite + offer + rejection insights matched for this platform
    reply_rate: float


class PlatformTrendsOut(BaseModel):
    platforms: list[PlatformTrend]
    summary: str  # one computed sentence, e.g. "Naukri has your highest reply rate (40%) across 10 applications."
