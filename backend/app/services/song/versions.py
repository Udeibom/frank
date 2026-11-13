"""
Pure versioning rules for the Song Record (song-record spec, requirement 3).

No I/O here, so the rules can be property-tested. The database layer stores what
these functions return and never changes a stored version.

Rules:
- A version is only ever added. Nothing is edited or removed.
- A version's parent must be an existing version of the same project and facet.
  The first version of a facet has no parent. After that, a parent is required.
- Restoring an earlier version adds a NEW version whose parent is the restored one.
- Only the user may write the intent statement (it stays in the user's words).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional, Sequence

from app.models.song import FACETS, USER_AUTHOR, FacetVersion


class VersionError(ValueError):
    """A write that would break a versioning rule."""


def _same_lane(v: FacetVersion, project_id: str, facet: str) -> bool:
    return v.project_id == project_id and v.facet == facet


def new_version(
    existing: Sequence[FacetVersion],
    *,
    project_id: str,
    facet: str,
    content: dict[str, Any],
    parent_id: Optional[str],
    operation: str,
    author: str,
    op_params: Optional[dict[str, Any]] = None,
    label: Optional[str] = None,
    version_id: Optional[str] = None,
) -> FacetVersion:
    """Build the next version of a facet, or raise VersionError."""
    if facet not in FACETS:
        raise VersionError(f"unknown facet: {facet}")
    if facet == "intent" and author != USER_AUTHOR:
        raise VersionError("only the user can change the intent statement")

    lane = [v for v in existing if _same_lane(v, project_id, facet)]
    if parent_id is None:
        if lane:
            raise VersionError("a parent version is required after the first version")
    else:
        if not any(v.id == parent_id for v in lane):
            raise VersionError("parent must be an existing version of the same project and facet")

    new_id = version_id or str(uuid.uuid4())
    if any(v.id == new_id for v in existing):
        raise VersionError("version id already exists")

    return FacetVersion(
        id=new_id,
        project_id=project_id,
        facet=facet,
        content=dict(content),
        parent_id=parent_id,
        operation=operation,
        op_params=dict(op_params or {}),
        author=author,
        label=label,
    )


def lineage(existing: Sequence[FacetVersion], version_id: str) -> list[FacetVersion]:
    """The chain from the first version down to `version_id`. Raises on a cycle or a gap."""
    by_id = {v.id: v for v in existing}
    if version_id not in by_id:
        raise VersionError("unknown version")
    chain: list[FacetVersion] = []
    seen: set[str] = set()
    current: Optional[FacetVersion] = by_id[version_id]
    while current is not None:
        if current.id in seen:
            raise VersionError("cycle in version lineage")
        seen.add(current.id)
        chain.append(current)
        if current.parent_id is None:
            break
        current = by_id.get(current.parent_id)
        if current is None:
            raise VersionError("version points at a missing parent")
    chain.reverse()
    return chain


def restore(
    existing: Sequence[FacetVersion],
    *,
    project_id: str,
    facet: str,
    version_id: str,
    author: str,
    version_new_id: Optional[str] = None,
) -> FacetVersion:
    """Add a new version holding an earlier version's content, with that version as its parent."""
    target = next(
        (v for v in existing if v.id == version_id and _same_lane(v, project_id, facet)),
        None,
    )
    if target is None:
        raise VersionError("version not found for this project and facet")
    return new_version(
        existing,
        project_id=project_id,
        facet=facet,
        content=target.content,
        parent_id=target.id,
        operation="restore",
        op_params={"restored_version_id": target.id},
        author=author,
        label=f"Restored: {target.label}" if target.label else "Restored",
        version_id=version_new_id,
    )


def heads(existing: Sequence[FacetVersion], project_id: str, facet: str) -> list[FacetVersion]:
    """Versions of a facet that no other version builds on (the tips of each branch)."""
    lane = [v for v in existing if _same_lane(v, project_id, facet)]
    parents = {v.parent_id for v in lane if v.parent_id}
    return [v for v in lane if v.id not in parents]
