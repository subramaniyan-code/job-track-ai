from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=schemas.ApplicationOut)
def create_application(
    payload: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    job = db.query(models.Job).filter(models.Job.id == payload.job_id).first()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    existing = db.query(models.Application).filter(
        models.Application.user_id == user.id, models.Application.job_id == job.id
    ).first()
    if existing:
        return existing

    app_row = models.Application(
        user_id=user.id,
        job_id=job.id,
        status=payload.status,
        resume_version=payload.resume_version,
        notes=payload.notes,
        recruiter_email=payload.recruiter_email,
        applied_at=datetime.utcnow() if payload.status == models.ApplicationStatus.applied else None,
    )
    db.add(app_row)
    db.commit()
    db.refresh(app_row)
    return app_row


@router.get("", response_model=list[schemas.ApplicationOut])
def list_applications(
    status_filter: models.ApplicationStatus | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.Application).filter(models.Application.user_id == user.id)
    if status_filter:
        query = query.filter(models.Application.status == status_filter)
    return query.order_by(models.Application.last_activity_at.desc()).all()


@router.patch("/{application_id}", response_model=schemas.ApplicationOut)
def update_application(
    application_id: str,
    payload: schemas.ApplicationUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    app_row = db.query(models.Application).filter(
        models.Application.id == application_id, models.Application.user_id == user.id
    ).first()
    if not app_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        app_row.status = data["status"]
        if data["status"] == models.ApplicationStatus.applied and not app_row.applied_at:
            app_row.applied_at = datetime.utcnow()
    for field in ("resume_version", "notes", "fit_score", "recruiter_email"):
        if field in data:
            setattr(app_row, field, data[field])

    app_row.last_activity_at = datetime.utcnow()
    db.commit()
    db.refresh(app_row)
    return app_row


@router.get("/{application_id}/apply-link")
def get_apply_link(
    application_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Returns the direct apply URL for one-tap manual submission.

    Design note: true unattended auto-apply against LinkedIn/Indeed's own
    forms violates their Terms of Service and is a common cause of account
    bans and recruiter blacklisting. This tool instead gets you to the
    verified apply page in one tap, with your tailored resume/tracking
    already prepared — the safe version of "auto apply".
    """
    app_row = db.query(models.Application).filter(
        models.Application.id == application_id, models.Application.user_id == user.id
    ).first()
    if not app_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return {"apply_url": app_row.job.url}


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    app_row = db.query(models.Application).filter(
        models.Application.id == application_id, models.Application.user_id == user.id
    ).first()
    if app_row:
        db.delete(app_row)
        db.commit()
