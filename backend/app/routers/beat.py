from fastapi import APIRouter

router = APIRouter(prefix="/projects/{project_id}/beat", tags=["beat"])


@router.post("/generate")
async def generate_beat(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/generate-section")
async def generate_section(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/add-stem")
async def add_stem(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/conversation")
async def beat_conversation(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.get("/versions")
async def list_beat_versions(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.post("/versions/active")
async def set_active_beat_version(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.patch("/sections/{section_id}")
async def update_section(project_id: str, section_id: str) -> dict:
    return {"status": "not_implemented"}
