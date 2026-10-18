"""
Central configuration, loaded from environment variables (see .env.example
at the project root). Nothing here should be hardcoded when you deploy.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Load settings directly from environment variables (GitHub secrets in CI).
    # No .env file is required in production.
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # --- Core ---
    # Database URL must be supplied via the DATABASE_URL secret; fallback for local development.
    database_url: str = os.getenv("DATABASE_URL", "postgresql://jobtrack:jobtrack@db:5432/jobtrack")
    # JWT secret must be a strong random string supplied via JWT_SECRET secret; fallback for local development.
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-please-use-a-long-random-string")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- Super admin bootstrap ---
    # Whoever registers with this email is automatically promoted to
    # super_admin on first registration. Everyone else who signs up
    # (e.g. your friends) gets the default "user" role.
    super_admin_email: str = "you@example.com"

    # --- Encryption key for storing per-user API keys / email passwords ---
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    secrets_encryption_key: str = ""

    # --- Optional global fallback job-source keys ---
    # If a user doesn't connect their own Adzuna key, these (if set) are
    # used as a shared fallback so the tool still works out of the box.
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    # --- Google AI (Gemini) for email analysis ---
    # Get a free key at https://aistudio.google.com/apikey
    google_ai_api_key: str = ""
    google_ai_model: str = "gemini-2.0-flash"

    # --- Inbox polling (kept conservative for small servers) ---
    inbox_poll_interval_minutes: int = 25
    inbox_max_emails_per_poll: int = 20
    # First-ever poll for a newly connected inbox looks back this many days.
    # A month of mail may exceed inbox_max_emails_per_poll in one run — the
    # poller processes oldest-first and advances its watermark each run, so
    # it simply catches up over several poll cycles rather than all at once.
    inbox_backfill_days: int = 30

    # --- CORS ---
    frontend_origin: str = "http://localhost:3000"


settings = Settings()
