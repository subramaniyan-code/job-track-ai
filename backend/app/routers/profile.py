from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..security import encrypt_str, decrypt_str
from ..services.resume_service import extract_text_from_file, parse_resume_with_ai

router = APIRouter(prefix="/profile", tags=["profile"])


def _to_profile_out(profile: models.CandidateProfile) -> schemas.CandidateProfileOut:
    return schemas.CandidateProfileOut(
        id=profile.id,
        full_name=profile.full_name,
        email=profile.email,
        phone=profile.phone,
        primary_roles=profile.primary_roles,
        skills=profile.skills,
        experience_years=profile.experience_years or 0.0,
        preferred_locations=profile.preferred_locations,
        naukri_search_queries=profile.naukri_search_queries,
        summary=profile.summary,
        resume_filename=profile.resume_filename,
        has_gemini_key=bool(profile.google_ai_api_key_encrypted),
        parser_source=profile.parser_source or "heuristic",
        parser_message=profile.parser_message,
        updated_at=profile.updated_at,
    )


@router.get("", response_model=schemas.CandidateProfileOut | None)
def get_candidate_profile(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    profile = db.query(models.CandidateProfile).filter(models.CandidateProfile.user_id == user.id).first()
    if not profile:
        return None
    return _to_profile_out(profile)


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

    # Handle Gemini API key update
    if "google_ai_api_key" in data:
        key_val = data.pop("google_ai_api_key")
        if key_val is not None:
            key_val = key_val.strip()
            if key_val:
                profile.google_ai_api_key_encrypted = encrypt_str(key_val)
            else:
                profile.google_ai_api_key_encrypted = None

    for field, val in data.items():
        setattr(profile, field, val)

    # Sync primary keywords and location to Naukri Bot Config
    bot_config = db.query(models.NaukriBotConfig).filter(models.NaukriBotConfig.user_id == user.id).first()
    if bot_config:
        if profile.naukri_search_queries:
            bot_config.target_keywords = ", ".join(profile.naukri_search_queries[:3])
        elif profile.primary_roles:
            bot_config.target_keywords = ", ".join(profile.primary_roles[:2])
        if profile.preferred_locations:
            bot_config.target_locations = ", ".join(profile.preferred_locations[:2])
        if profile.experience_years:
            bot_config.experience_years = int(profile.experience_years)

    db.commit()
    db.refresh(profile)
    return _to_profile_out(profile)


@router.post("/resume", response_model=schemas.CandidateProfileOut)
async def upload_and_parse_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Uploads a resume (PDF, DOCX, DOC), parses skills, roles, and experience
    with Google Gemini AI (or High-Precision Heuristic fallback), and auto-populates search profiles.
    """
    fn_lower = file.filename.lower()
    allowed_exts = (".pdf", ".docx", ".doc", ".txt")
    if not any(fn_lower.endswith(ext) for ext in allowed_exts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported formats: PDF (.pdf), Microsoft Word (.docx, .doc), or Text (.txt).",
        )

    file_bytes = await file.read()
    if len(file_bytes) > 15 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum limit of 15MB.",
        )

    try:
        raw_text = extract_text_from_file(file.filename, file_bytes)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not raw_text or len(raw_text.strip()) < 40:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract readable text from this document. Please ensure it contains selectable text.",
        )

    profile = db.query(models.CandidateProfile).filter(models.CandidateProfile.user_id == user.id).first()
    if not profile:
        profile = models.CandidateProfile(user_id=user.id)
        db.add(profile)

    # Check for user-configured Gemini key
    custom_key = None
    if profile.google_ai_api_key_encrypted:
        try:
            custom_key = decrypt_str(profile.google_ai_api_key_encrypted)
        except Exception:
            pass

    parsed = await parse_resume_with_ai(raw_text, custom_gemini_key=custom_key)

    profile.full_name = parsed.get("full_name") or profile.full_name or "Candidate"
    profile.email = parsed.get("email") or profile.email
    profile.phone = parsed.get("phone") or profile.phone
    profile.primary_roles = parsed.get("primary_roles") or []
    profile.skills = parsed.get("skills") or []
    profile.experience_years = float(parsed.get("experience_years") or 0.0)
    profile.preferred_locations = parsed.get("preferred_locations") or ["Chennai", "Remote"]
    profile.naukri_search_queries = parsed.get("naukri_search_queries") or []
    profile.summary = parsed.get("summary")
    profile.resume_filename = file.filename
    profile.parser_source = parsed.get("parser_source") or "heuristic"
    profile.parser_message = parsed.get("parser_message")

    # Sync keywords to Naukri Bot config
    bot_config = db.query(models.NaukriBotConfig).filter(models.NaukriBotConfig.user_id == user.id).first()
    if not bot_config:
        bot_config = models.NaukriBotConfig(
            user_id=user.id,
            target_keywords=", ".join(parsed.get("naukri_search_queries", [])[:2] or parsed.get("primary_roles", [])[:2]),
            target_locations=", ".join(parsed.get("preferred_locations", [])[:2]),
            experience_years=int(parsed.get("experience_years") or 0),
        )
        db.add(bot_config)
    else:
        # Update with freshly extracted search keywords
        bot_config.target_keywords = ", ".join(parsed.get("naukri_search_queries", [])[:2] or parsed.get("primary_roles", [])[:2])
        bot_config.target_locations = ", ".join(parsed.get("preferred_locations", [])[:2])
        bot_config.experience_years = int(parsed.get("experience_years") or 0)

    db.commit()
    db.refresh(profile)
    return _to_profile_out(profile)
