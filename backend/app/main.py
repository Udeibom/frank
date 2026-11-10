from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth import require_project_access
from app.config import get_settings
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

app = FastAPI(
    title="Frank API",
    description="The backend for Frank — a music production platform for non-musicians.",
    version="0.1.0",
)

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
