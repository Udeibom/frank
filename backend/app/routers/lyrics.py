from fastapi import APIRouter

router = APIRouter(prefix="/projects/{project_id}/lyrics", tags=["lyrics"])


@router.get("")
async def list_lyrics_versions(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("")
async def save_lyrics_version(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.get("/{version_id}")
async def get_lyrics_version(project_id: str, version_id: str) -> dict:
    return {"status": "not_implemented"}


@router.patch("/{version_id}")
async def update_lyrics_version(project_id: str, version_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/active")
async def set_active_lyrics(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/voice-memo")
async def transcribe_voice_memo(project_id: str) -> dict:
    return {"status": "not_implemented"}
