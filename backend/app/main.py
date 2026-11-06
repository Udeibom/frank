from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
app.include_router(projects.router)
app.include_router(lyrics.router)
app.include_router(feel.router)
app.include_router(beat.router)
app.include_router(voice.router)
app.include_router(mix.router)
app.include_router(export.router)
app.include_router(conversation.router)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "service": "frank-api"}
