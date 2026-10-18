from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user

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
