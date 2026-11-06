from fastapi import APIRouter

router = APIRouter(prefix="/projects/{project_id}/voice", tags=["voice"])


@router.post("/takes")
async def upload_take(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.get("/takes")
async def list_takes(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.delete("/takes/{take_id}")
async def delete_take(project_id: str, take_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/takes/{take_id}/correct")
async def correct_pitch(project_id: str, take_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/comp")
async def generate_comp(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/harmony")
async def generate_harmony(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/conversation")
async def voice_conversation(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/active")
async def set_active_vocal(project_id: str) -> dict:
    return {"status": "not_implemented"}
