import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..security import decrypt_dict
from ..connectors.registry import get_connector
from ..config import settings
from ..services.platform import infer_platform

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/search", response_model=list[schemas.JobOut])
async def search_jobs(
    payload: schemas.JobSearchRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    connections = db.query(models.ApiConnection).filter(
        models.ApiConnection.user_id == user.id, models.ApiConnection.is_active == True  # noqa: E712
    ).all()

    # Fall back to a shared Adzuna key (if the admin configured one) so the
    # tool works even before a user connects their own API keys.
    if not connections and settings.adzuna_app_id and settings.adzuna_app_key:
        connections = [models.ApiConnection(
            provider=models.ConnectorProvider.adzuna,
            credentials_encrypted=None,  # handled specially below
        )]

    async def run_one(conn: models.ApiConnection):
        if conn.credentials_encrypted:
            creds = decrypt_dict(conn.credentials_encrypted)
        else:
            creds = {"app_id": settings.adzuna_app_id, "app_key": settings.adzuna_app_key, "country": "in"}
        connector = get_connector(conn.provider, creds)
        try:
            return await connector.search(payload.keywords, payload.location, payload.remote_only, payload.max_results)
        except Exception:
            return []

    results_per_source = await asyncio.gather(*(run_one(c) for c in connections))

    saved_jobs: list[models.Job] = []
    for conn, normalized_jobs in zip(connections, results_per_source):
        for nj in normalized_jobs:
            existing = db.query(models.Job).filter(
                models.Job.source == conn.provider.value, models.Job.external_id == nj.external_id
            ).first()
            if existing:
                saved_jobs.append(existing)
                continue
            job = models.Job(
                source=conn.provider.value,
                external_id=nj.external_id,
                title=nj.title,
                company=nj.company,
                location=nj.location,
                remote=nj.remote,
                url=nj.url,
                platform=infer_platform(url=nj.url),
                description=nj.description,
                posted_at=nj.posted_at,
                raw=nj.raw,
            )
            db.add(job)
            saved_jobs.append(job)

    db.commit()
    for j in saved_jobs:
        db.refresh(j)
    return saved_jobs


@router.post("/manual", response_model=schemas.JobOut)
def create_manual_job(
    payload: schemas.JobManualCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """For jobs found outside any connected source — Naukri, LinkedIn, a
    company's own careers page, a referral, wherever. Creates a trackable
    Job record directly, no connector involved."""
    job = models.Job(
        source="manual",
        external_id=f"manual-{user.id}-{datetime.utcnow().timestamp()}",
        title=payload.title,
        company=payload.company,
        location=payload.location,
        remote=payload.remote,
        url=payload.url or "",
        platform=infer_platform(url=payload.url) if payload.url else "Other",
        description=payload.description,
        posted_at=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[schemas.JobOut])
def list_jobs(
    q: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.Job)
    if q:
        query = query.filter(models.Job.title.ilike(f"%{q}%"))
    return query.order_by(models.Job.fetched_at.desc()).limit(limit).all()
