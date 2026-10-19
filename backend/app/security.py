import json
from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet
from jose import jwt, JWTError
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, extra: Optional[dict] = None) -> str:
    to_encode = {"sub": subject, "exp": datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)}
    if extra:
        to_encode.update(extra)
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# --- Encryption for per-user API keys / SMTP passwords stored at rest ---
def _fernet() -> Fernet:
    key = settings.secrets_encryption_key
    if not key:
        raise RuntimeError(
            "SECRETS_ENCRYPTION_KEY is not set. Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "and put it in your .env file."
        )
    try:
        return Fernet(key.encode())
    except Exception:
        import base64
        import hashlib
        derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        return Fernet(derived)


def encrypt_dict(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_dict(token: str) -> dict:
    return json.loads(_fernet().decrypt(token.encode()).decode())


def encrypt_str(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_str(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
