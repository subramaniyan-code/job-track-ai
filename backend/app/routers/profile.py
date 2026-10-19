from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..services.resume_service import extract_text_from_pdf, parse_resume_with_ai

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=schemas.CandidateProfileOut | None)
def get_candidate_profile(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return db.query(models.CandidateProfile).filter(models.CandidateProfile.user_id == user.id).first()


@router.put("", response_model=schemas.CandidateProfileOut)
def update_candidate_profile(
    payload: schemas.CandidateProfileUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    profile = db.query(models.CandidateProfile).filter(models.CandidateProfile.user_id == user.id).first()
    if not profile:
        profile = models.CandidateProfile(user_id=user.id)
        db.add(profile)

    data = payload.model_dump(exclude_unset=True)
    for field, val in data.items():
        setattr(profile, field, val)

    db.commit()
    db.refresh(profile)
    return profile


@router.post("/resume", response_model=schemas.CandidateProfileOut)
async def upload_and_parse_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Uploads a PDF resume, parses skills/keywords with Gemini AI, and auto-populates search profiles."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF format is currently supported for resume parsing.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum limit of 10MB.",
        )

    try:
        raw_text = extract_text_from_pdf(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not raw_text or len(raw_text.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract text from this PDF. Please ensure it contains readable text (not scanned images).",
        )

    parsed = await parse_resume_with_ai(raw_text)

    profile = db.query(models.CandidateProfile).filter(models.CandidateProfile.user_id == user.id).first()
    if not profile:
        profile = models.CandidateProfile(user_id=user.id)
        db.add(profile)

    profile.full_name = parsed.get("full_name") or profile.full_name
    profile.email = parsed.get("email") or profile.email
    profile.phone = parsed.get("phone") or profile.phone
    profile.primary_roles = parsed.get("primary_roles") or []
    profile.skills = parsed.get("skills") or []
    profile.experience_years = float(parsed.get("experience_years") or 0.0)
    profile.preferred_locations = parsed.get("preferred_locations") or ["Bengaluru", "Remote"]
    profile.naukri_search_queries = parsed.get("naukri_search_queries") or []
    profile.summary = parsed.get("summary")
    profile.raw_resume_text = raw_text[:10000]
    profile.resume_filename = file.filename

    # Also automatically sync keywords to the Naukri Bot configuration if present
    bot_config = db.query(models.NaukriBotConfig).filter(models.NaukriBotConfig.user_id == user.id).first()
    if not bot_config:
        bot_config = models.NaukriBotConfig(
            user_id=user.id,
            target_keywords=", ".join(parsed.get("naukri_search_queries", [])[:2] or parsed.get("primary_roles", [])[:2]),
            target_locations=", ".join(parsed.get("preferred_locations", [])[:2]),
            experience_years=int(parsed.get("experience_years") or 0),
        )
        db.add(bot_config)
    elif not bot_config.target_keywords:
        bot_config.target_keywords = ", ".join(parsed.get("naukri_search_queries", [])[:2] or parsed.get("primary_roles", [])[:2])
        bot_config.target_locations = ", ".join(parsed.get("preferred_locations", [])[:2])
        bot_config.experience_years = int(parsed.get("experience_years") or 0)

    db.commit()
    db.refresh(profile)
    return profile
