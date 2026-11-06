from fastapi import APIRouter

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.post("/idea/{project_id}")
async def idea_conversation(project_id: str) -> dict:
    return {"status": "not_implemented"}
