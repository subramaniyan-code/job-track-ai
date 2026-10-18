from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .config import settings
from .scheduler import start_scheduler
from .routers import auth, connectors, jobs, applications, followups, dashboard, email_account, admin, inbox


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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
