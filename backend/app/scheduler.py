import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .database import SessionLocal
from . import models
from .config import settings
from .services.email_service import send_email
from .services.imap_service import fetch_new_job_emails
from .services.gemini_service import classify_email
from .services.platform import infer_platform

log = logging.getLogger("scheduler")


async def dispatch_due_followups():
    """
    Runs every few minutes. Sends any follow-up that's been explicitly
    approved by the user AND whose suggested send time has arrived.
    Nothing is ever sent without a prior human approval via /followups/{id}/approve.
    """
    db = SessionLocal()
    try:
        due = db.query(models.FollowUp).filter(
            models.FollowUp.status == models.FollowUpStatus.approved,
            models.FollowUp.suggested_send_at <= datetime.utcnow(),
        ).all()

        for fu in due:
            app_row = db.query(models.Application).filter(models.Application.id == fu.application_id).first()
            if not app_row or not app_row.recruiter_email:
                continue
            email_account = db.query(models.EmailAccount).filter(models.EmailAccount.user_id == fu.user_id).first()
            if not email_account or not email_account.is_active:
                continue
            try:
                await send_email(email_account, app_row.recruiter_email, fu.subject, fu.body)
                fu.status = models.FollowUpStatus.sent
                fu.sent_at = datetime.utcnow()
                db.commit()
            except Exception:
                log.exception("Failed to send scheduled follow-up %s", fu.id)
    finally:
        db.close()


def _find_matching_application(db, user_id: str, company: str | None):
    """Best-effort match of an inbox reply to a tracked application, by
    company name. Deliberately simple — exact heuristics are less important
    than never crashing or blocking the poll loop."""
    if not company:
        return None
    apps = db.query(models.Application).filter(models.Application.user_id == user_id).all()
    company_lower = company.lower()
    for app in apps:
        if app.job and app.job.company and company_lower in app.job.company.lower():
            return app
    return None


async def poll_one_account(db, account: models.EmailAccount, force_backfill: bool = False, raise_on_error: bool = False):
    fetched, new_watermark = await asyncio.to_thread(fetch_new_job_emails, account, force_backfill, raise_on_error)

    new_insights_count = 0
    for msg in fetched:
        # Dedup: skip anything we've already stored for this user.
        exists = db.query(models.EmailInsight).filter(
            models.EmailInsight.user_id == account.user_id,
            models.EmailInsight.message_id == msg.message_id,
        ).first()
        if exists:
            continue

        classification = await classify_email(msg.from_address, msg.subject, msg.body)
        if not classification or classification.type == "other":
            continue

        matched_app = _find_matching_application(db, account.user_id, classification.company)

        insight = models.EmailInsight(
            user_id=account.user_id,
            message_id=msg.message_id,
            from_address=msg.from_address,
            subject=msg.subject,
            received_at=msg.received_at,
            insight_type=classification.type,
            company=classification.company,
            job_title=classification.job_title,
            platform=infer_platform(email_address=msg.from_address),
            summary=classification.summary,
            matched_application_id=matched_app.id if matched_app else None,
            extracted_jobs=classification.extracted_jobs or None,
        )
        db.add(insight)
        new_insights_count += 1

        # A detected reply is itself useful signal — bump the matched
        # application's last_activity_at so it surfaces as recently active.
        if matched_app:
            matched_app.last_activity_at = datetime.utcnow()

    account.last_seen_uid = new_watermark
    db.commit()
    return new_insights_count, len(fetched)


async def poll_all_inboxes():
    """
    Runs on an interval (default every 25 min — see settings.inbox_poll_interval_minutes).
    Processes one connected inbox at a time, sequentially, to keep memory
    bounded on small servers. A failure on one account is logged and skipped
    rather than stopping the whole run.
    """
    db = SessionLocal()
    try:
        accounts = db.query(models.EmailAccount).filter(
            models.EmailAccount.imap_enabled == True,  # noqa: E712
            models.EmailAccount.is_active == True,      # noqa: E712
        ).all()

        for account in accounts:
            try:
                await poll_one_account(db, account)
            except Exception:
                log.exception("Inbox poll failed for account %s", account.id)
                db.rollback()
    finally:
        db.close()


def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(dispatch_due_followups, "interval", minutes=5, id="dispatch_due_followups")
    scheduler.add_job(
        poll_all_inboxes, "interval",
        minutes=settings.inbox_poll_interval_minutes,
        id="poll_all_inboxes",
        max_instances=1,  # never let two polls overlap on a small server
        coalesce=True,    # if a run was missed, don't queue up back-to-back catch-ups
    )
    scheduler.start()
    return scheduler
