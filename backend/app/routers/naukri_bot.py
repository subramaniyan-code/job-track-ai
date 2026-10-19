import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db, SessionLocal
from ..deps import get_current_user
from ..security import encrypt_str
from ..services.naukri_bot import run_naukri_auto_apply_session

router = APIRouter(prefix="/naukri-bot", tags=["naukri-bot"])


def _to_config_out(cfg: models.NaukriBotConfig) -> schemas.NaukriBotConfigOut:
    return schemas.NaukriBotConfigOut(
        id=cfg.id,
        enabled=cfg.enabled,
        has_session=bool(cfg.session_cookies_encrypted),
        daily_max_applications=cfg.daily_max_applications,
        runs_per_day=cfg.runs_per_day,
        target_keywords=cfg.target_keywords,
        target_locations=cfg.target_locations,
        experience_years=cfg.experience_years,
        applications_today=cfg.applications_today,
        last_run_at=cfg.last_run_at,
        next_run_at=cfg.next_run_at,
        status=cfg.status or "idle",
        status_message=cfg.status_message,
        updated_at=cfg.updated_at,
    )


@router.get("/config", response_model=schemas.NaukriBotConfigOut)
def get_naukri_bot_config(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    cfg = db.query(models.NaukriBotConfig).filter(models.NaukriBotConfig.user_id == user.id).first()
    if not cfg:
        cfg = models.NaukriBotConfig(
            user_id=user.id,
            enabled=False,
            daily_max_applications=5,
            runs_per_day=3,
            status="idle",
            status_message="Bot is ready to be configured. Upload your resume and add your session cookies to begin.",
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return _to_config_out(cfg)


@router.put("/config", response_model=schemas.NaukriBotConfigOut)
def update_naukri_bot_config(
    payload: schemas.NaukriBotConfigUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    cfg = db.query(models.NaukriBotConfig).filter(models.NaukriBotConfig.user_id == user.id).first()
    if not cfg:
        cfg = models.NaukriBotConfig(user_id=user.id)
        db.add(cfg)

    data = payload.model_dump(exclude_unset=True)
    if "daily_max_applications" in data:
        # Enforce maximum safety cap of 10
        data["daily_max_applications"] = min(10, max(1, data["daily_max_applications"]))
    if "runs_per_day" in data:
        data["runs_per_day"] = min(4, max(1, data["runs_per_day"]))

    for k, v in data.items():
        setattr(cfg, k, v)

    db.commit()
    db.refresh(cfg)
    return _to_config_out(cfg)


@router.post("/session", response_model=schemas.NaukriBotConfigOut)
def save_naukri_session(
    payload: schemas.NaukriSessionPayload,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Securely encrypts and stores Naukri session cookies for the Playwright worker."""
    raw = payload.cookies_json.strip()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cookies JSON cannot be empty.")

    cfg = db.query(models.NaukriBotConfig).filter(models.NaukriBotConfig.user_id == user.id).first()
    if not cfg:
        cfg = models.NaukriBotConfig(user_id=user.id)
        db.add(cfg)

    cfg.session_cookies_encrypted = encrypt_str(raw)
    cfg.status = "idle"
    cfg.status_message = "Naukri session cookies updated and encrypted successfully."
    db.commit()
    db.refresh(cfg)
    return _to_config_out(cfg)


@router.post("/run-now")
async def trigger_naukri_run_now(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Immediately triggers an on-demand stealth auto-apply session."""
    cfg = db.query(models.NaukriBotConfig).filter(models.NaukriBotConfig.user_id == user.id).first()
    if not cfg or not cfg.session_cookies_encrypted:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Naukri session is not configured yet. Please paste your session cookies in Auto-Apply settings.",
        )

    if cfg.status == "running":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A browsing session is already in progress. Please wait for it to finish.",
        )

    # Run in background task to avoid blocking the HTTP request
    async def _run_job():
        job_db = SessionLocal()
        try:
            bot_cfg = job_db.query(models.NaukriBotConfig).filter(models.NaukriBotConfig.id == cfg.id).first()
            if bot_cfg:
                await run_naukri_auto_apply_session(job_db, bot_cfg)
        finally:
            job_db.close()

    asyncio.create_task(_run_job())

    return {
        "status": "started",
        "message": "Stealth Naukri browsing session started in background. Check the Audit Log in 2 minutes for updates.",
    }


@router.get("/logs", response_model=list[schemas.NaukriBotLogOut])
def get_naukri_bot_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.NaukriBotLog)
        .filter(models.NaukriBotLog.user_id == user.id)
        .order_by(models.NaukriBotLog.created_at.desc())
        .limit(limit)
        .all()
    )
