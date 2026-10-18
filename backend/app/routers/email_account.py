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
    if not account:
        account = models.EmailAccount(user_id=user.id, smtp_username=payload.smtp_username, smtp_host=payload.smtp_host,
                                       smtp_password_encrypted=encrypt_str(payload.smtp_password))
        db.add(account)

    account.smtp_host = payload.smtp_host
    account.smtp_port = payload.smtp_port
    account.smtp_username = payload.smtp_username
    account.smtp_password_encrypted = encrypt_str(payload.smtp_password)
    account.from_name = payload.from_name

    account.imap_host = payload.imap_host or _SMTP_TO_IMAP.get(payload.smtp_host)
    account.imap_port = payload.imap_port
    account.imap_enabled = payload.imap_enabled and bool(account.imap_host)

    db.commit()
    db.refresh(account)
    return account


@router.delete("", status_code=204)
def delete_email_account(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    account = db.query(models.EmailAccount).filter(models.EmailAccount.user_id == user.id).first()
    if account:
        db.delete(account)
        db.commit()
