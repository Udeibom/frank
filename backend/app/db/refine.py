"""refine_proposals table (migration 007, spec 08)."""
from __future__ import annotations

from typing import Any, Optional

from app.db.client import get_supabase


def insert_proposal(row: dict[str, Any]) -> dict:
    return get_supabase().table("refine_proposals").insert(row).execute().data[0]


def get_proposal(proposal_id: str) -> Optional[dict]:
    rows = get_supabase().table("refine_proposals").select("*").eq("id", proposal_id).limit(1).execute().data
    return rows[0] if rows else None


def find_by_idempotency(project_id: str, idempotency_key: str) -> Optional[dict]:
    rows = (get_supabase().table("refine_proposals").select("*")
            .eq("project_id", project_id).eq("idempotency_key", idempotency_key)
            .limit(1).execute().data)
    return rows[0] if rows else None


def latest_proposals(project_id: str, limit: int = 5) -> list[dict]:
    return (get_supabase().table("refine_proposals").select("*").eq("project_id", project_id)
            .order("created_at", desc=True).limit(limit).execute().data or [])


def update_direction(proposal_id: str, n: int, fields: dict[str, Any]) -> None:
    """Fill in a direction's preview. Read-modify-write; previews run one at a time behind the heavy gate."""
    row = get_proposal(proposal_id)
    if not row:
        return
    directions = list(row.get("directions") or [])
    if 0 <= n < len(directions):
        directions[n] = {**directions[n], **fields}
        get_supabase().table("refine_proposals").update({"directions": directions}).eq("id", proposal_id).execute()


def set_chosen(proposal_id: str, n: int, job_id: str | None = None) -> bool:
    table = get_supabase().table("refine_proposals")
    if job_id:
        result = (table.update({"chosen_job_id": job_id})
                  .eq("id", proposal_id).eq("chosen", n).execute())
        return bool(result.data)
    result = (table.update({"chosen": n})
              .eq("id", proposal_id).is_("chosen", None).execute())
    return bool(result.data)
