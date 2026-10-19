from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..security import encrypt_str

router = APIRouter(prefix="/email-account", tags=["email-account"])

# Common provider host pairs — if the user only fills in SMTP, we can guess
# the matching IMAP host rather than making them look it up.
_SMTP_TO_IMAP = {
    "smtp.gmail.com": "imap.gmail.com",
    "smtp-mail.outlook.com": "outlook.office365.com",
    "smtp.office365.com": "outlook.office365.com",
    "smtp.mail.yahoo.com": "imap.mail.yahoo.com",
}


@router.get("", response_model=schemas.EmailAccountOut | None)
def get_email_account(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.EmailAccount).filter(models.EmailAccount.user_id == user.id).first()


@router.put("", response_model=schemas.EmailAccountOut)
def upsert_email_account(
    payload: schemas.EmailAccountCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    account = db.query(models.EmailAccount).filter(models.EmailAccount.user_id == user.id).first()
    
    clean_pwd = (payload.smtp_password or "").strip()
    # Normalize 16-character Gmail app passwords that users copy with spaces
    if ("gmail" in (payload.imap_host or payload.smtp_host).lower()) and len(clean_pwd.replace(" ", "")) == 16:
        clean_pwd = clean_pwd.replace(" ", "")

    if not account:
        if not clean_pwd:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password is required when connecting a new email account.")
        account = models.EmailAccount(
            user_id=user.id,
            smtp_username=payload.smtp_username.strip(),
            smtp_host=payload.smtp_host.strip(),
            smtp_password_encrypted=encrypt_str(clean_pwd),
        )
        db.add(account)
    elif clean_pwd:
        account.smtp_password_encrypted = encrypt_str(clean_pwd)

    account.smtp_host = payload.smtp_host.strip()
    account.smtp_port = payload.smtp_port
    account.smtp_username = payload.smtp_username.strip()
    account.from_name = payload.from_name.strip() if payload.from_name else None

    account.imap_host = (payload.imap_host.strip() if payload.imap_host else None) or _SMTP_TO_IMAP.get(account.smtp_host, "imap.gmail.com" if "gmail" in account.smtp_host else None)
    account.imap_port = payload.imap_port or 993
    account.imap_enabled = payload.imap_enabled and bool(account.imap_host)

    db.commit()
    db.refresh(account)
    return account


@router.post("/test")
def test_email_account(
    payload: schemas.EmailAccountCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Verifies that the provided credentials can successfully log into IMAP."""
    import imaplib
    from ..security import decrypt_str

    clean_pwd = (payload.smtp_password or "").strip()
    if not clean_pwd:
        account = db.query(models.EmailAccount).filter(models.EmailAccount.user_id == user.id).first()
        if account and account.smtp_password_encrypted:
            clean_pwd = decrypt_str(account.smtp_password_encrypted)

    if not clean_pwd:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please provide an App Password to test connection.")

    imap_host = (payload.imap_host.strip() if payload.imap_host else None) or _SMTP_TO_IMAP.get(payload.smtp_host, "imap.gmail.com" if "gmail" in payload.smtp_host else payload.smtp_host)
    imap_port = payload.imap_port or 993

    if ("gmail" in imap_host.lower()) and len(clean_pwd.replace(" ", "")) == 16:
        clean_pwd = clean_pwd.replace(" ", "")

    try:
        conn = imaplib.IMAP4_SSL(imap_host, imap_port)
        conn.login(payload.smtp_username.strip(), clean_pwd)
        status_, data = conn.select("INBOX", readonly=True)
        count = data[0].decode() if data and data[0] else "0"
        conn.logout()
        return {
            "status": "ok",
            "message": f"Successfully connected to {imap_host}! INBOX contains {count} messages.",
        }
    except Exception as e:
        err = str(e)
        if "AUTHENTICATIONFAILED" in err:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Authentication failed: Gmail requires a 16-character App Password (not your regular Gmail password). Generate one at myaccount.google.com/apppasswords and ensure IMAP is enabled in Gmail Settings -> Forwarding and POP/IMAP.",
            )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"IMAP connection failed ({imap_host}:{imap_port}): {err}",
        )


@router.delete("", status_code=204)
def delete_email_account(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    account = db.query(models.EmailAccount).filter(models.EmailAccount.user_id == user.id).first()
    if account:
        db.delete(account)
        db.commit()
