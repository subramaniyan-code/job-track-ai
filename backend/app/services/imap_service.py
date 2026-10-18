"""
Reads job-related email from the user's own inbox via IMAP.

Deliberately conservative for a small (~1GB RAM) server:
  - stdlib `imaplib` only — no extra heavy dependency
  - fetches at most `settings.inbox_max_emails_per_poll` messages per run
  - only looks at mail newer than the last-seen UID (stored per account)
  - truncates body text before it's ever handed to the AI classifier
  - one account processed at a time, synchronously — no concurrent IMAP
    connections that could spike memory
"""
import email
import imaplib
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Optional

from .. import models
from ..config import settings
from ..security import decrypt_str

MAX_BODY_CHARS = 4000

# Senders/subject keywords that usually mean "this is job-related" — used to
# skip everything else cheaply, before any AI call is made (AI calls cost
# money and CPU; this filter keeps both down).
JOB_SENDER_HINTS = [
    "naukri.com", "linkedin.com", "indeed.com", "shine.com", "foundit.in",
    "monsterindia.com", "greenhouse.io", "lever.co", "workday.com",
    "smartrecruiters.com", "myworkday.com", "icims.com", "ashbyhq.com",
]
JOB_SUBJECT_HINTS = [
    "application", "applied", "interview", "job alert", "new jobs",
    "shortlisted", "offer", "hiring", "recruiter", "position", "opportunity",
    "we've received your application", "thank you for applying",
]


@dataclass
class FetchedEmail:
    uid: str
    message_id: str
    from_address: str
    subject: str
    received_at: Optional[datetime]
    body: str


def _decode(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(text)
    return "".join(out)


def _looks_job_related(sender: str, subject: str) -> bool:
    s = (sender or "").lower()
    subj = (subject or "").lower()
    return any(h in s for h in JOB_SENDER_HINTS) or any(h in subj for h in JOB_SUBJECT_HINTS)


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                except Exception:
                    continue
        # fall back to first html part if no plain text found
        for part in msg.walk():
            if part.get_content_type() == "text/html" and not part.get("Content-Disposition"):
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                except Exception:
                    continue
        return ""
    else:
        try:
            return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
        except Exception:
            return str(msg.get_payload())


def fetch_new_job_emails(account: models.EmailAccount) -> tuple[list[FetchedEmail], Optional[str]]:
    """
    Connects, fetches up to `inbox_max_emails_per_poll` new messages since
    `account.last_seen_uid`, filters to job-related ones, and returns them
    plus the new watermark UID to persist (caller's responsibility to save).
    Returns ([], None) on any connection failure rather than raising, so one
    broken account never takes down the scheduler loop for everyone else.
    """
    password = decrypt_str(account.smtp_password_encrypted) if not account.imap_host else decrypt_str(account.smtp_password_encrypted)
    results: list[FetchedEmail] = []
    new_watermark = account.last_seen_uid

    try:
        conn = imaplib.IMAP4_SSL(account.imap_host, account.imap_port or 993)
        conn.login(account.smtp_username, password)
        conn.select("INBOX", readonly=True)

        if account.last_seen_uid:
            search_criterion = f"(UID {int(account.last_seen_uid) + 1}:*)"
        else:
            # First run ever for this account: don't backfill the whole
            # mailbox (could be years of mail) — just the configured window
            # (default 30 days). If that window has more mail than one poll
            # can process, we take the OLDEST batch first (see below) and
            # advance the watermark forward, so later polls pick up right
            # where this one left off instead of jumping straight to "now"
            # and silently skipping everything in between.
            since_date = (datetime.utcnow() - timedelta(days=settings.inbox_backfill_days)).strftime("%d-%b-%Y")
            search_criterion = f'(SINCE "{since_date}")'

        status_, data = conn.uid("search", None, search_criterion)
        if status_ != "OK" or not data or not data[0]:
            conn.logout()
            return [], new_watermark

        # Oldest-first, capped per run. Taking the newest N instead would
        # permanently skip older mail once the watermark jumps past it —
        # this way a big backfill is simply spread across several poll
        # cycles until it's fully caught up.
        uids = data[0].split()[:settings.inbox_max_emails_per_poll]

        for uid in uids:
            uid_str = uid.decode()
            status_, msg_data = conn.uid("fetch", uid, "(RFC822)")
            if status_ != "OK" or not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            sender = _decode(msg.get("From", ""))
            subject = _decode(msg.get("Subject", ""))

            if not _looks_job_related(sender, subject):
                new_watermark = uid_str
                continue

            body = _extract_body(msg)[:MAX_BODY_CHARS]
            date_hdr = msg.get("Date")
            try:
                received_at = parsedate_to_datetime(date_hdr) if date_hdr else None
            except Exception:
                received_at = None

            results.append(FetchedEmail(
                uid=uid_str,
                message_id=msg.get("Message-ID", uid_str),
                from_address=sender,
                subject=subject,
                received_at=received_at,
                body=body,
            ))
            new_watermark = uid_str

        conn.logout()
    except Exception:
        # Connection/auth failure, bad credentials, network hiccup, etc.
        # Fail quietly — the scheduler will just try again next interval.
        return [], account.last_seen_uid

    return results, new_watermark
