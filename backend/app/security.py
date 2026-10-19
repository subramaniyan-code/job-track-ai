import base64
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet, MultiFernet
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


# --- Encryption for per-user API keys / SMTP passwords / session cookies stored at rest ---
def _derive_fernet_key(raw: str) -> bytes:
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> MultiFernet:
    keys: list[Fernet] = []

    # 1. Primary: user-configured secrets_encryption_key
    if settings.secrets_encryption_key:
        k = settings.secrets_encryption_key.strip()
        try:
            keys.append(Fernet(k.encode("utf-8")))
        except Exception:
            pass
        try:
            keys.append(Fernet(_derive_fernet_key(k)))
        except Exception:
            pass

    # 2. Secondary fallback: derive from jwt_secret (always non-empty)
    if settings.jwt_secret:
        try:
            keys.append(Fernet(_derive_fernet_key(settings.jwt_secret.strip())))
        except Exception:
            pass

    # 3. Static fallback so decryption never crashes if key was rotated
    try:
        keys.append(Fernet(_derive_fernet_key("jobtrack-ai-static-salt-key-2026")))
    except Exception:
        pass

    if not keys:
        keys.append(Fernet(Fernet.generate_key()))

    return MultiFernet(keys)


def encrypt_dict(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode("utf-8")).decode("utf-8")


def decrypt_dict(token: str) -> dict:
    if not token:
        return {}
    try:
        decrypted_bytes = _fernet().decrypt(token.encode("utf-8"))
        return json.loads(decrypted_bytes.decode("utf-8"))
    except Exception:
        return {}


def encrypt_str(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_str(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""
