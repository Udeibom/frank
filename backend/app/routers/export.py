from fastapi import APIRouter

router = APIRouter(prefix="/projects/{project_id}/export", tags=["export"])


@router.post("")
async def create_export(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.get("")
async def list_exports(project_id: str) -> dict:
    return {"status": "not_implemented"}


@router.get("/{export_id}/download")
async def get_download_url(project_id: str, export_id: str) -> dict:
    return {"status": "not_implemented"}
