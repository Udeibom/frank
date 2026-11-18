"""
Taste memory routes (spec 09, requirement 4). The person's own taste, across all their songs: see it in plain
words, edit any line, forget a line or everything. Forgetting deletes. Only ever the caller's own rows.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.services.taste import store

router = APIRouter(prefix="/taste", tags=["taste"])


class EditRequest(BaseModel):
    statement: str = Field(min_length=3, max_length=300)


def _shape(r: dict) -> dict:
    return {"id": r["id"], "statement": r["statement"], "said_by_you": r["status"] == "user_stated",
            "edited": bool(r.get("edited_by_user")), "about": r["specialist"], "updated_at": str(r.get("updated_at"))}


@router.get("")
async def list_taste(user_id: str = Depends(get_current_user_id)) -> dict:
    rows = await asyncio.to_thread(store.preferences, user_id)
    return {"items": [_shape(r) for r in rows]}


@router.patch("/{pref_id}")
async def edit_taste(pref_id: str, body: EditRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    row = await asyncio.to_thread(store.edit, user_id, pref_id, body.statement.strip())
    if not row:
        raise HTTPException(status_code=404, detail="I can't find that line.")
    return _shape(row)


@router.delete("/{pref_id}")
async def forget_line(pref_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    if not await asyncio.to_thread(store.forget, user_id, pref_id):
        raise HTTPException(status_code=404, detail="I can't find that line.")
    return {"status": "forgotten"}


@router.delete("")
async def forget_everything(user_id: str = Depends(get_current_user_id)) -> dict:
    await asyncio.to_thread(store.forget_all, user_id)
    return {"status": "forgotten"}
