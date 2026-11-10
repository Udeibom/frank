import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth import require_project_access
from app.middleware.signed_urls import SignedUrlMiddleware
from app.config import get_settings
from app.db import jobs as jobs_db
from app.services.jobs.staleness import RESTART_MESSAGE, with_retries
from app.routers import (
    projects,
    lyrics,
    feel,
    beat,
    voice,
    mix,
    export,
    conversation,
    jobs,
)

settings = get_settings()
log = logging.getLogger("frank.startup")


async def _sweep_orphaned_jobs(started_at: datetime) -> None:
    """Jobs run inside this process, so any job still active from before this
    start belonged to a process that is gone (job-reliability spec 3.1)."""
    try:
        # Retried: a single network blip at boot must not leave orphans behind.
        # (Seen live: "Server disconnected" on the first attempt.)
        n = await asyncio.wait_for(
            with_retries(
                lambda: jobs_db.fail_jobs_active_before(RESTART_MESSAGE, started_at),
                attempts=5,
                base_delay=2.0,
            ),
            timeout=120,
        )
        log.info("startup: marked %d orphaned job(s) as failed", n)
    except Exception:  # noqa: BLE001 — never block or crash startup (3.2)
        log.warning("startup: could not sweep orphaned jobs", exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    started_at = datetime.now(timezone.utc)
    # Background task so a slow network can't delay the server coming up.
    sweep = asyncio.create_task(_sweep_orphaned_jobs(started_at))
    yield
    sweep.cancel()


app = FastAPI(
    title="Frank API",
    description="The backend for Frank — a music production platform for non-musicians.",
    version="0.1.0",
    lifespan=lifespan,
)

# Added BEFORE CORS so CORS stays the outermost layer (later = outer).
app.add_middleware(SignedUrlMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
# projects.py authenticates and checks ownership per route (it owns the
# /projects and /projects/{id} paths). Every router mounted under
# /projects/{project_id}/... gets the ownership check ONCE here, so a route added
# later cannot forget it (auth spec, requirement 5.4).
app.include_router(projects.router)
_owned = [Depends(require_project_access)]
app.include_router(lyrics.router, dependencies=_owned)
app.include_router(feel.router, dependencies=_owned)
app.include_router(beat.router, dependencies=_owned)
app.include_router(voice.router, dependencies=_owned)
app.include_router(mix.router, dependencies=_owned)
app.include_router(export.router, dependencies=_owned)
app.include_router(conversation.router, dependencies=_owned)
# jobs.py checks job -> project ownership inside its route.
app.include_router(jobs.router)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "service": "frank-api"}
