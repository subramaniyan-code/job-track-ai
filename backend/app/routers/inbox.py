from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..scheduler import poll_one_account, backfill_unmatched_insights

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.get("", response_model=list[schemas.EmailInsightOut])
def list_inbox(
    unread_only: bool = False,
    limit: int = 30,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.EmailInsight).filter(models.EmailInsight.user_id == user.id)
    if unread_only:
        query = query.filter(models.EmailInsight.is_read == False)  # noqa: E712
    return query.order_by(models.EmailInsight.created_at.desc()).limit(limit).all()


@router.post("/sync")
async def sync_inbox_now(
    force_backfill: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Trigger an immediate IMAP poll and email classification for this user's inbox."""
    account = db.query(models.EmailAccount).filter(
        models.EmailAccount.user_id == user.id,
        models.EmailAccount.is_active == True,  # noqa: E712
    ).first()
    if not account:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No email account connected. Please connect your Gmail or Outlook account in Settings first.",
        )

    # Auto-enable IMAP if user clicked sync
    if not account.imap_enabled or not account.imap_host:
        account.imap_enabled = True
        if not account.imap_host:
            if "gmail" in account.smtp_host or "gmail" in account.smtp_username:
                account.imap_host = "imap.gmail.com"
            elif "outlook" in account.smtp_host or "office365" in account.smtp_host:
                account.imap_host = "outlook.office365.com"
            else:
                account.imap_host = account.smtp_host
        account.imap_port = account.imap_port or 993
        db.commit()

    try:
        new_count, fetched_count = await poll_one_account(db, account, force_backfill=force_backfill, raise_on_error=True)
        backfill_unmatched_insights(db)
    except Exception as e:
        error_text = str(e)
        if "AUTHENTICATIONFAILED" in error_text:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Email login failed: Gmail requires a 16-character App Password (not your normal Gmail password). Please generate one in Google Account Security (myaccount.google.com/apppasswords) and update in Settings.",
            )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Email inbox connection failed: {error_text}",
        )

    recent_count = db.query(models.EmailInsight).filter(
        models.EmailInsight.user_id == user.id
    ).count()

    return {
        "status": "ok",
        "new_insights": new_count,
        "scanned_job_emails": fetched_count,
        "total_insights": recent_count,
    }


@router.post("/{insight_id}/mark-read", response_model=schemas.EmailInsightOut)
def mark_read(insight_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    insight = db.query(models.EmailInsight).filter(
        models.EmailInsight.id == insight_id, models.EmailInsight.user_id == user.id
    ).first()
    if not insight:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    insight.is_read = True
    db.commit()
    db.refresh(insight)
    return insight
