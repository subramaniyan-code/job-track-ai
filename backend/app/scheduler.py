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


def _auto_track_or_update_application(
    db,
    user_id: str,
    classification_type: str,
    company: str | None,
    job_title: str | None,
    platform: str | None,
    message_id: str,
    subject: str,
    body: str,
    received_at: datetime | None,
    recruiter_email: str | None = None,
    recruiter_phone: str | None = None,
) -> models.Application | None:
    """Creates a new tracked application if one doesn't exist, or advances status and saves recruiter contact."""
    if classification_type not in ["application_confirmation", "interview_invite", "offer", "rejection"]:
        return None

    matched_app = _find_matching_application(db, user_id, company)
    company_name = company or "Direct Application"
    title = job_title or (f"Role at {company_name}" if company else (subject[:60] if subject else "Job Application"))
    platform_name = platform or "Email"
    received_time = received_at or datetime.utcnow()

    status_map = {
        "application_confirmation": models.ApplicationStatus.applied,
        "interview_invite": models.ApplicationStatus.interviewing,
        "offer": models.ApplicationStatus.offer,
        "rejection": models.ApplicationStatus.rejected,
    }
    target_status = status_map.get(classification_type, models.ApplicationStatus.applied)

    if not matched_app:
        # Create Job
        job = models.Job(
            source="email",
            external_id=f"email-{message_id}",
            title=title,
            company=company_name,
            platform=platform_name,
            url="",
            description=body[:1000] if body else None,
            posted_at=received_time,
        )
        db.add(job)
        db.flush()

        # Create Application
        matched_app = models.Application(
            user_id=user_id,
            job_id=job.id,
            status=target_status,
            recruiter_email=recruiter_email,
            recruiter_phone=recruiter_phone,
            applied_at=received_time,
            last_activity_at=received_time,
            notes=f"Auto-tracked from email: {subject}",
        )
        db.add(matched_app)
        db.flush()

        db.add(models.ApplicationEvent(
            application_id=matched_app.id,
            user_id=user_id,
            event_type="imported",
            to_status=target_status.value,
            note=f"Imported from {classification_type} email: {subject[:100]}",
        ))
    else:
        # Store recruiter contact details if newly found
        if recruiter_email and not matched_app.recruiter_email:
            matched_app.recruiter_email = recruiter_email
        if recruiter_phone and not matched_app.recruiter_phone:
            matched_app.recruiter_phone = recruiter_phone

        # Advance status
        if classification_type == "application_confirmation":
            if matched_app.status == models.ApplicationStatus.saved:
                matched_app.status = models.ApplicationStatus.applied
                matched_app.applied_at = received_time
        elif matched_app.status != target_status:
            prev = matched_app.status.value if hasattr(matched_app.status, "value") else str(matched_app.status)
            matched_app.status = target_status
            db.add(models.ApplicationEvent(
                application_id=matched_app.id,
                user_id=user_id,
                event_type="status_change",
                from_status=prev,
                to_status=target_status.value,
                note=f"Status updated via email: {subject[:100]}",
            ))
        matched_app.last_activity_at = datetime.utcnow()

    return matched_app


def backfill_unmatched_insights(db):
    """
    Scans existing email insights and creates/links application records for any
    application confirmations, interview invites, rejections, or offers that were
    previously stored without an application row.
    """
    unmatched = db.query(models.EmailInsight).filter(
        models.EmailInsight.matched_application_id == None,
        models.EmailInsight.insight_type.in_([
            models.EmailInsightType.application_confirmation,
            models.EmailInsightType.interview_invite,
            models.EmailInsightType.offer,
            models.EmailInsightType.rejection,
        ]),
    ).all()

    for ins in unmatched:
        itype = ins.insight_type.value if hasattr(ins.insight_type, "value") else str(ins.insight_type)
        app = _auto_track_or_update_application(
            db=db,
            user_id=ins.user_id,
            classification_type=itype,
            company=ins.company,
            job_title=ins.job_title,
            platform=ins.platform,
            message_id=ins.message_id,
            subject=ins.subject or "",
            body="",
            received_at=ins.received_at,
        )
        if app:
            ins.matched_application_id = app.id

    db.commit()


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
            if not exists.body and msg.body:
                exists.body = msg.body
                db.commit()
            continue

        classification = await classify_email(msg.from_address, msg.subject, msg.body)
        if not classification or classification.type == "other":
            continue

        platform_str = infer_platform(email_address=msg.from_address)
        matched_app = _auto_track_or_update_application(
            db=db,
            user_id=account.user_id,
            classification_type=classification.type,
            company=classification.company,
            job_title=classification.job_title,
            platform=platform_str,
            message_id=msg.message_id,
            subject=msg.subject,
            body=msg.body,
            received_at=msg.received_at,
            recruiter_email=classification.recruiter_email,
            recruiter_phone=classification.recruiter_phone,
        )

        insight = models.EmailInsight(
            user_id=account.user_id,
            message_id=msg.message_id,
            from_address=msg.from_address,
            subject=msg.subject,
            received_at=msg.received_at,
            body=msg.body,
            insight_type=classification.type,
            company=classification.company,
            job_title=classification.job_title,
            platform=platform_str,
            summary=classification.summary,
            matched_application_id=matched_app.id if matched_app else None,
            extracted_jobs=classification.extracted_jobs or None,
        )
        db.add(insight)
        new_insights_count += 1

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


async def poll_naukri_bots():
    """
    Checks if any enabled Naukri bots are due for a scheduled session.
    Runs periodically (every 30 min), evaluates human hours (09:00 - 20:00 IST),
    and executes randomized sessions if due.
    """
    from .services.naukri_bot import run_naukri_auto_apply_session

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # Indian Standard Time (UTC + 5:30) check: only run between 9:00 AM and 8:00 PM IST (3:30 to 14:30 UTC)
        hour_utc = now.hour + now.minute / 60.0
        is_ist_daytime = 3.5 <= hour_utc <= 14.5

        if not is_ist_daytime:
            return

        configs = db.query(models.NaukriBotConfig).filter(
            models.NaukriBotConfig.enabled == True,
            models.NaukriBotConfig.session_cookies_encrypted != None,
        ).all()

        for cfg in configs:
            if cfg.status == "running":
                continue

            today_str = now.strftime("%Y-%m-%d")
            if cfg.last_reset_date != today_str:
                cfg.applications_today = 0
                cfg.last_reset_date = today_str
                db.commit()

            if cfg.applications_today >= cfg.daily_max_applications:
                continue

            # Minimum spacing between sessions based on user's runs_per_day
            min_interval_seconds = max(7200, int((10 * 3600) / max(1, cfg.runs_per_day)))
            if cfg.last_run_at:
                elapsed = (now - cfg.last_run_at).total_seconds()
                if elapsed < min_interval_seconds:
                    continue

            try:
                await run_naukri_auto_apply_session(db, cfg)
            except Exception:
                log.exception("Naukri bot session failed for user %s", cfg.user_id)
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
    scheduler.add_job(
        poll_naukri_bots, "interval",
        minutes=30,
        id="poll_naukri_bots",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler

