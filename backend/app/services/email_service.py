import aiosmtplib
from email.message import EmailMessage

from .. import models
from ..security import decrypt_str


async def send_email(email_account: models.EmailAccount, to_address: str, subject: str, body: str):
    """Sends via the user's own connected SMTP account (e.g. a Gmail App Password),
    so follow-ups genuinely come from the user's inbox, not a shared no-reply address."""
    password = decrypt_str(email_account.smtp_password_encrypted)

    msg = EmailMessage()
    msg["From"] = f"{email_account.from_name} <{email_account.smtp_username}>" if email_account.from_name else email_account.smtp_username
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    await aiosmtplib.send(
        msg,
        hostname=email_account.smtp_host,
        port=email_account.smtp_port,
        username=email_account.smtp_username,
        password=password,
        start_tls=True,
    )
