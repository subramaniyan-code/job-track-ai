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
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import html
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Optional

from .. import models
from ..config import settings
from ..security import decrypt_str

log = logging.getLogger("imap")

MAX_BODY_CHARS = 20000

# Senders/subject keywords that usually mean "this is job-related" — used to
# skip everything else cheaply, before any AI call is made (AI calls cost
# money and CPU; this filter keeps both down).
JOB_SENDER_HINTS = [
    "naukri", "linkedin", "indeed", "shine.com", "foundit.in", "monsterindia.com",
    "greenhouse.io", "lever.co", "workday.com", "smartrecruiters.com", "myworkday.com",
    "myworkdayjobs.com", "icims.com", "ashbyhq.com", "glassdoor.com", "instahyre.com",
    "hirist.com", "cutshort.io", "apna.co", "internshala.com", "wellfound.com",
    "angel.co", "talview.com", "hackerrank.com", "codility.com", "hirevue.com",
]

JOB_SUBJECT_HINTS = [
    "application", "applied", "interview", "job alert", "new jobs",
    "shortlisted", "offer", "hiring", "recruiter", "position", "opportunity",
    "we've received your application", "thank you for applying", "candidacy",
    "candidate", "assessment", "screening", "invitation", "test", "status",
    "career", "careers", "resume", "role", "round", "submission",
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


def _clean_html_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    # Convert line breaks and paragraph/block closures to real newlines
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw_html)
    text = re.sub(r"(?i)</(?:p|div|tr|li|h[1-6]|table|blockquote)>", "\n", text)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    # Clean up whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        txt = payload.decode(part.get_content_charset() or "utf-8", errors="ignore").strip()
                        if txt:
                            return txt
                except Exception:
                    continue
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        raw_html = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                        clean = _clean_html_text(raw_html)
                        if clean:
                            return clean
                except Exception:
                    continue
        return ""
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                txt = payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")
                if msg.get_content_type() == "text/html":
                    txt = _clean_html_text(txt)
                return txt
            return str(msg.get_payload() or "")
        except Exception:
            return str(msg.get_payload() or "")


def fetch_new_job_emails(
    account: models.EmailAccount,
    force_backfill: bool = False,
    raise_on_error: bool = False,
) -> tuple[list[FetchedEmail], Optional[str]]:
    """
    Connects to IMAP, searches recent emails, fast-scans headers for job-related messages,
    downloads matching bodies, and returns them plus the updated UID watermark.
    """
    password = decrypt_str(account.smtp_password_encrypted) if account.smtp_password_encrypted else ""
    if not password:
        err = "No password stored for this email account. Please update your App Password in Settings."
        log.error(err)
        if raise_on_error:
            raise ValueError(err)
        return [], account.last_seen_uid

    imap_host = account.imap_host or "imap.gmail.com"
    imap_port = account.imap_port or 993

    if ("gmail" in imap_host.lower()) and len(password.replace(" ", "")) == 16:
        password = password.replace(" ", "")
    else:
        password = password.strip()

    results: list[FetchedEmail] = []
    new_watermark = account.last_seen_uid

    try:
        log.info("Connecting to IMAP host %s:%s for user %s", imap_host, imap_port, account.smtp_username)
        conn = imaplib.IMAP4_SSL(imap_host, imap_port)
        conn.login(account.smtp_username.strip(), password)
        conn.select("INBOX", readonly=True)

        utcnow = datetime.utcnow()
        if account.last_seen_uid and not force_backfill:
            search_criterion = f"(UID {int(account.last_seen_uid) + 1}:*)"
        else:
            since_dt = utcnow - timedelta(days=settings.inbox_backfill_days)
            since_str = f"{since_dt.day}-{since_dt.strftime('%b')}-{since_dt.year}"
            search_criterion = f'(SINCE "{since_str}")'

        log.info("Running IMAP search with criterion: %s", search_criterion)
        status_, data = conn.uid("search", None, search_criterion)
        if status_ != "OK" or not data or not data[0]:
            conn.logout()
            log.info("No matching messages found in IMAP search.")
            return [], new_watermark

        uids = data[0].split()
        total_found = len(uids)
        log.info("Found %d total messages in search window", total_found)
        if total_found == 0:
            conn.logout()
            return [], new_watermark

        target_uids = uids[-150:] if total_found > 150 else uids

        uid_set_str = b",".join(target_uids).decode()
        status_, header_items = conn.uid(
            "fetch",
            uid_set_str,
            "(UID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])",
        )

        matched_job_uids: list[tuple[str, str, str, email.message.Message]] = []
        if status_ == "OK" and header_items:
            for item in header_items:
                if not (isinstance(item, tuple) and len(item) == 2):
                    continue
                info = item[0].decode(errors="ignore")
                raw_hdr = item[1]
                msg_hdr = email.message_from_bytes(raw_hdr)

                uid_match = re.search(r"UID\s+(\d+)", info, re.IGNORECASE)
                if not uid_match:
                    continue
                uid_str = uid_match.group(1)

                sender = _decode(msg_hdr.get("From", ""))
                subject = _decode(msg_hdr.get("Subject", ""))

                if _looks_job_related(sender, subject):
                    matched_job_uids.append((uid_str, sender, subject, msg_hdr))

        log.info(
            "Identified %d job-related emails out of %d scanned headers. Downloading full content...",
            len(matched_job_uids),
            len(target_uids),
        )

        to_fetch = matched_job_uids[-settings.inbox_max_emails_per_poll:]
        for uid_str, sender, subject, msg_hdr in to_fetch:
            status_, full_data = conn.uid("fetch", uid_str, "(RFC822)")
            if status_ != "OK" or not full_data or not full_data[0] or not isinstance(full_data[0], tuple):
                continue

            full_msg = email.message_from_bytes(full_data[0][1])
            body = _extract_body(full_msg)[:MAX_BODY_CHARS]
            date_hdr = msg_hdr.get("Date") or full_msg.get("Date")
            try:
                if date_hdr:
                    dt = parsedate_to_datetime(date_hdr)
                    if dt and dt.tzinfo is not None:
                        received_at = dt.astimezone(timezone.utc).replace(tzinfo=None)
                    else:
                        received_at = dt
                else:
                    received_at = None
            except Exception:
                received_at = None

            results.append(FetchedEmail(
                uid=uid_str,
                message_id=msg_hdr.get("Message-ID") or full_msg.get("Message-ID") or uid_str,
                from_address=sender,
                subject=subject,
                received_at=received_at,
                body=body,
            ))

        new_watermark = uids[-1].decode()
        conn.logout()
        log.info("Successfully fetched %d job-related emails from inbox.", len(results))
    except Exception as e:
        log.error("IMAP error for %s: %s", account.smtp_username, e, exc_info=True)
        if raise_on_error:
            raise
        return [], account.last_seen_uid

    return results, new_watermark
