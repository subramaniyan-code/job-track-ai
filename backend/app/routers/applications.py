import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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
        salary_expectation=payload.salary_expectation,
        applied_at=datetime.utcnow() if payload.status == models.ApplicationStatus.applied else None,
    )
    db.add(app_row)
    db.commit()
    db.refresh(app_row)

    # Log creation event
    db.add(models.ApplicationEvent(
        application_id=app_row.id,
        user_id=user.id,
        event_type="created",
        to_status=payload.status.value,
    ))
    db.commit()
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


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Download all applications as a CSV file."""
    apps = db.query(models.Application).filter(
        models.Application.user_id == user.id
    ).order_by(models.Application.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Title", "Company", "Location", "Platform", "Status",
        "Applied At", "Salary Expectation", "Recruiter Email", "Recruiter Phone",
        "Resume Version", "Fit Score", "Notes", "Created At",
    ])
    for a in apps:
        writer.writerow([
            a.job.title,
            a.job.company or "",
            a.job.location or "",
            a.job.platform or "",
            a.status.value,
            a.applied_at.isoformat() if a.applied_at else "",
            a.salary_expectation or "",
            a.recruiter_email or "",
            a.recruiter_phone or "",
            a.resume_version or "",
            a.fit_score if a.fit_score is not None else "",
            a.notes or "",
            a.created_at.isoformat(),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=applications.csv"},
    )


@router.get("/stale", response_model=list[schemas.ApplicationOut])
def get_stale_applications(
    days: int = 7,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Applications with status=applied and no activity for N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    return db.query(models.Application).filter(
        models.Application.user_id == user.id,
        models.Application.status == models.ApplicationStatus.applied,
        models.Application.last_activity_at < cutoff,
    ).order_by(models.Application.last_activity_at.asc()).limit(10).all()


@router.get("/{application_id}/timeline", response_model=list[schemas.ApplicationEventOut])
def get_timeline(
    application_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    app_row = db.query(models.Application).filter(
        models.Application.id == application_id, models.Application.user_id == user.id
    ).first()
    if not app_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return db.query(models.ApplicationEvent).filter(
        models.ApplicationEvent.application_id == application_id
    ).order_by(models.ApplicationEvent.created_at.asc()).all()


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
    old_status = app_row.status

    if "status" in data:
        new_status = data["status"]
        app_row.status = new_status
        if new_status == models.ApplicationStatus.applied and not app_row.applied_at:
            app_row.applied_at = datetime.utcnow()
        if new_status != old_status:
            db.add(models.ApplicationEvent(
                application_id=app_row.id,
                user_id=user.id,
                event_type="status_change",
                from_status=old_status.value,
                to_status=new_status.value,
            ))

    for field in ("resume_version", "notes", "fit_score", "recruiter_email", "recruiter_phone", "salary_expectation"):
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
