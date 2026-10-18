from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..services.followup_templates import TEMPLATES, render_template
from ..services.send_time import suggest_send_time
from ..services.email_service import send_email

router = APIRouter(prefix="/followups", tags=["followups"])


@router.get("/templates")
def list_templates():
    """So the UI can show a picker of prebuilt humble-professional templates."""
    return {key: tpl["label"] for key, tpl in TEMPLATES.items()}


@router.post("/draft", response_model=schemas.FollowUpOut)
def draft_followup(
    payload: schemas.FollowUpDraftRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    app_row = db.query(models.Application).filter(
        models.Application.id == payload.application_id, models.Application.user_id == user.id
    ).first()
    if not app_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    applied_date_str = app_row.applied_at.strftime("%B %d, %Y") if app_row.applied_at else "recently"
    rendered = render_template(
        payload.template,
        job_title=app_row.job.title,
        company=app_row.job.company or "there",
        applied_date=applied_date_str,
        your_name=user.full_name,
    )
    if payload.tone_note:
        rendered["body"] += f"\n\n[Note for review: {payload.tone_note}]"

    reference = app_row.applied_at or app_row.created_at
    send_at = suggest_send_time(payload.template, reference, user.timezone)

    followup = models.FollowUp(
        application_id=app_row.id,
        user_id=user.id,
        subject=rendered["subject"],
        body=rendered["body"],
        template_used=payload.template,
        status=models.FollowUpStatus.draft,
        suggested_send_at=send_at,
    )
    db.add(followup)
    db.commit()
    db.refresh(followup)
    return followup


@router.get("", response_model=list[schemas.FollowUpOut])
def list_followups(
    status_filter: models.FollowUpStatus | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.FollowUp).filter(models.FollowUp.user_id == user.id)
    if status_filter:
        query = query.filter(models.FollowUp.status == status_filter)
    return query.order_by(models.FollowUp.suggested_send_at.asc()).all()


@router.patch("/{followup_id}", response_model=schemas.FollowUpOut)
def edit_followup(
    followup_id: str,
    payload: schemas.FollowUpUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    fu = db.query(models.FollowUp).filter(models.FollowUp.id == followup_id, models.FollowUp.user_id == user.id).first()
    if not fu:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Follow-up not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(fu, field, value)
    db.commit()
    db.refresh(fu)
    return fu


@router.post("/{followup_id}/approve", response_model=schemas.FollowUpOut)
def approve_followup(followup_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    Marks a follow-up approved. The scheduler picks up approved follow-ups
    and sends them at their suggested_send_at time. Use /send-now to skip
    the wait and send immediately.
    """
    fu = db.query(models.FollowUp).filter(models.FollowUp.id == followup_id, models.FollowUp.user_id == user.id).first()
    if not fu:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Follow-up not found")
    fu.status = models.FollowUpStatus.approved
    db.commit()
    db.refresh(fu)
    return fu


@router.post("/{followup_id}/skip", response_model=schemas.FollowUpOut)
def skip_followup(followup_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fu = db.query(models.FollowUp).filter(models.FollowUp.id == followup_id, models.FollowUp.user_id == user.id).first()
    if not fu:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Follow-up not found")
    fu.status = models.FollowUpStatus.skipped
    db.commit()
    db.refresh(fu)
    return fu


@router.post("/{followup_id}/send-now", response_model=schemas.FollowUpOut)
async def send_now(followup_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fu = db.query(models.FollowUp).filter(models.FollowUp.id == followup_id, models.FollowUp.user_id == user.id).first()
    if not fu:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Follow-up not found")

    app_row = db.query(models.Application).filter(models.Application.id == fu.application_id).first()
    if not app_row.recruiter_email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add a recruiter/contact email on the application first")

    email_account = db.query(models.EmailAccount).filter(models.EmailAccount.user_id == user.id).first()
    if not email_account:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Connect your email account in Settings first")

    await send_email(email_account, app_row.recruiter_email, fu.subject, fu.body)

    fu.status = models.FollowUpStatus.sent
    fu.sent_at = datetime.utcnow()
    db.commit()
    db.refresh(fu)
    return fu
