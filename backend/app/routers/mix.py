from fastapi import APIRouter

router = APIRouter(prefix="/projects/{project_id}/mix", tags=["mix"])


@router.post("/render")
async def render_mix(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.get("/versions")
async def list_mix_versions(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/versions/active")
async def set_active_mix_version(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/conversation")
async def mix_conversation(project_id: str) -> dict:
    return {"status": "not_implemented"}
