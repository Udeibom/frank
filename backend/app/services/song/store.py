"""
Writes to the Song Record. Applies the pure rules in versions.py, then stores
the result. Other services (intake, specialists) call these functions so every
change gets lineage, an author, and an operation name.
"""

from __future__ import annotations

from typing import Any, Optional

from postgrest.exceptions import APIError

from app.db import song as song_db
from app.models.song import FacetVersion
from app.services.song import versions as rules


_UNIQUE_VIOLATION = "23505"
_MAX_ATTEMPTS = 4


def _is_root_conflict(exc: APIError) -> bool:
    """Two writers both tried to create the first version of a facet; the database kept one."""
    return getattr(exc, "code", None) == _UNIQUE_VIOLATION


async def write_facet(
    project_id: str,
    facet: str,
    content: dict[str, Any],
    *,
    author: str,
    operation: str,
    parent_id: Optional[str] = None,
    op_params: Optional[dict[str, Any]] = None,
    label: Optional[str] = None,
    activate: bool = True,
) -> FacetVersion:
    """
    Add a new version of a facet. The parent defaults to the facet's current active
    version, so a plain "set" extends the current line; passing another parent
    starts a branch.
    """
    caller_chose_parent = parent_id is not None
    for attempt in range(_MAX_ATTEMPTS):
        existing = await song_db.list_versions(project_id, facet)
        parent = parent_id
        if parent is None and existing:
            active = (await song_db.get_active_map(project_id)).get(facet)
            parent = active or rules.heads(existing, project_id, facet)[-1].id

        version = rules.new_version(
            existing,
            project_id=project_id,
            facet=facet,
            content=content,
            parent_id=parent,
            operation=operation,
            op_params=op_params,
            author=author,
            label=label,
        )
        try:
            stored = await song_db.insert_version(version)
        except APIError as exc:
            # Someone else wrote the first version a moment ago. Look again: now there is a
            # parent to build on. (A caller who named a parent is not retried: their parent
            # must already exist, so this cannot be that race.)
            if _is_root_conflict(exc) and not caller_chose_parent and attempt + 1 < _MAX_ATTEMPTS:
                continue
            raise
        if activate:
            await song_db.set_active(project_id, facet, stored.id)
        return stored
    raise rules.VersionError("could not save after several attempts")  # pragma: no cover


async def restore_facet(
    project_id: str, facet: str, version_id: str, *, author: str
) -> FacetVersion:
    """Go back to an earlier version. Adds a new version (parent = the restored one) and makes it active."""
    existing = await song_db.list_versions(project_id, facet)
    version = rules.restore(
        existing, project_id=project_id, facet=facet, version_id=version_id, author=author
    )
    stored = await song_db.insert_version(version)
    await song_db.set_active(project_id, facet, stored.id)
    return stored


async def activate_facet_version(project_id: str, facet: str, version_id: str) -> None:
    """Switch which version is live. Instant; creates nothing."""
    existing = await song_db.list_versions(project_id, facet)
    if not any(v.id == version_id for v in existing):
        raise rules.VersionError("version not found for this project and facet")
    await song_db.set_active(project_id, facet, version_id)
