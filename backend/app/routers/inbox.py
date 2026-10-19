from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..scheduler import poll_one_account

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
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Trigger an immediate IMAP poll and Gemini classification for this user's inbox."""
    account = db.query(models.EmailAccount).filter(
        models.EmailAccount.user_id == user.id,
        models.EmailAccount.imap_enabled == True,  # noqa: E712
        models.EmailAccount.is_active == True,      # noqa: E712
    ).first()
    if not account:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No email account with IMAP enabled found. Please connect your email in Settings first.",
        )

    await poll_one_account(db, account)

    recent_count = db.query(models.EmailInsight).filter(
        models.EmailInsight.user_id == user.id
    ).count()

    return {"status": "ok", "total_insights": recent_count}


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
