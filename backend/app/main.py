from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .config import settings
from .scheduler import start_scheduler
from .routers import auth, connectors, jobs, applications, followups, dashboard, email_account, admin, inbox


def run_migrations():
    from sqlalchemy import text
    from .database import SessionLocal
    from .scheduler import backfill_unmatched_insights
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS salary_expectation VARCHAR;"))
            conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_min FLOAT;"))
            conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_max FLOAT;"))
            conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_currency VARCHAR DEFAULT 'INR';"))
    except Exception:
        pass

    try:
        db = SessionLocal()
        backfill_unmatched_insights(db)
        db.close()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations()
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="JobTrack AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_origin_regex=r"^https?://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(connectors.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(followups.router)
app.include_router(dashboard.router)
app.include_router(email_account.router)
app.include_router(admin.router)
app.include_router(inbox.router)


@app.get("/health")
def health():
    return {"status": "ok"}
