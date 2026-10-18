from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

REPLY_STATUSES = {models.ApplicationStatus.interviewing, models.ApplicationStatus.offer, models.ApplicationStatus.rejected}
REPLY_INSIGHT_TYPES = {models.EmailInsightType.interview_invite, models.EmailInsightType.offer, models.EmailInsightType.rejection}


@router.get("/stats", response_model=schemas.DashboardStats)
def get_stats(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    apps = db.query(models.Application).filter(models.Application.user_id == user.id).all()

    total = len(apps)
    applied = sum(1 for a in apps if a.status != models.ApplicationStatus.saved)
    interviewing = sum(1 for a in apps if a.status == models.ApplicationStatus.interviewing)
    offers = sum(1 for a in apps if a.status == models.ApplicationStatus.offer)
    rejected = sum(1 for a in apps if a.status == models.ApplicationStatus.rejected)
    ghosted = sum(1 for a in apps if a.status == models.ApplicationStatus.ghosted)

    responded = interviewing + offers + rejected
    response_rate = round((responded / applied) * 100, 1) if applied else 0.0

    now = datetime.utcnow()
    last_7 = sum(1 for a in apps if a.applied_at and a.applied_at >= now - timedelta(days=7))
    last_30 = sum(1 for a in apps if a.applied_at and a.applied_at >= now - timedelta(days=30))

    pending_followups = db.query(models.FollowUp).filter(
        models.FollowUp.user_id == user.id,
        models.FollowUp.status.in_([models.FollowUpStatus.draft, models.FollowUpStatus.approved]),
    ).count()

    unread_inbox = db.query(models.EmailInsight).filter(
        models.EmailInsight.user_id == user.id,
        models.EmailInsight.is_read == False,  # noqa: E712
    ).count()

    return schemas.DashboardStats(
        total_applications=total,
        applied=applied,
        interviewing=interviewing,
        offers=offers,
        rejected=rejected,
        ghosted=ghosted,
        response_rate=response_rate,
        pending_followups=pending_followups,
        applications_last_7_days=last_7,
        applications_last_30_days=last_30,
        unread_inbox_insights=unread_inbox,
    )


@router.get("/platform-trends", response_model=schemas.PlatformTrendsOut)
def get_platform_trends(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    Which platforms (Naukri, LinkedIn, Indeed, Shine, direct company sites,
    etc.) you've actually applied through, and which ones are getting you
    replies. Computed with plain counting — deliberately no AI call here,
    to keep this fast and free to load on every dashboard visit.
    """
    apps = db.query(models.Application).filter(models.Application.user_id == user.id).all()

    # A reply-type EmailInsight matched to an application is also a sign the
    # employer responded, even if the user hasn't manually updated status yet.
    replied_app_ids = {
        row.matched_application_id
        for row in db.query(models.EmailInsight.matched_application_id).filter(
            models.EmailInsight.user_id == user.id,
            models.EmailInsight.insight_type.in_(REPLY_INSIGHT_TYPES),
            models.EmailInsight.matched_application_id.isnot(None),
        ).all()
    }

    buckets: dict[str, dict[str, int]] = {}
    for app in apps:
        platform = (app.job.platform if app.job and app.job.platform else "Other") or "Other"
        bucket = buckets.setdefault(platform, {"applied": 0, "replies": 0})
        bucket["applied"] += 1
        if app.status in REPLY_STATUSES or app.id in replied_app_ids:
            bucket["replies"] += 1

    platforms = [
        schemas.PlatformTrend(
            platform=name,
            applied=counts["applied"],
            replies=counts["replies"],
            reply_rate=round((counts["replies"] / counts["applied"]) * 100, 1) if counts["applied"] else 0.0,
        )
        for name, counts in buckets.items()
    ]
    platforms.sort(key=lambda p: p.applied, reverse=True)

    total_applied = sum(p.applied for p in platforms)
    if total_applied == 0:
        summary = "No applications tracked yet \u2014 start tracking to see platform trends here."
    else:
        # Only consider platforms with enough volume for the rate to mean anything.
        meaningful = [p for p in platforms if p.applied >= 2]
        top = max(meaningful, key=lambda p: p.reply_rate) if meaningful else None
        platform_word = "platform" if len(platforms) == 1 else "platforms"
        summary = f"You've applied to {total_applied} roles across {len(platforms)} {platform_word}."
        if top and top.reply_rate > 0:
            summary += f" {top.platform} has your best reply rate so far \u2014 {top.reply_rate}% across {top.applied} applications."
        elif top:
            summary += f" No replies yet on your highest-volume platform ({top.platform}, {top.applied} applications) \u2014 might be worth a follow-up."

    return schemas.PlatformTrendsOut(platforms=platforms, summary=summary)
