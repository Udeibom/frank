"""
Authentication and project ownership.

- get_current_user_id: validates the caller's Supabase access token by asking
  Supabase Auth, so it works with either legacy or asymmetric JWT signing keys
  and needs no signing secret on our side. A validated token is cached briefly.
- require_project_access: one dependency, mounted on every project-scoped router,
  that makes sure the project belongs to the caller. Missing and foreign
  projects look identical (404) so an id's existence is never confirmed.

The pure decision functions (bypass_allowed, owns_project) are kept free of I/O
so they can be property-tested.
"""
from __future__ import annotations

import time
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Request
from postgrest.exceptions import APIError

from app.config import Settings, get_settings
from app.db import projects as projects_db

_CACHE_TTL_SECONDS = 60.0
_CACHE_MAX_ENTRIES = 500
# token -> (user_id, expires_at_monotonic)
_token_cache: dict[str, tuple[str, float]] = {}


def bypass_allowed(settings: Settings) -> bool:
    """The dev bypass applies only in development AND when explicitly disabled."""
    return settings.environment == "development" and not settings.auth_required


def owns_project(project: Optional[dict], user_id: str) -> bool:
    """True only when the project exists and belongs to this user."""
    return bool(project) and bool(user_id) and project.get("user_id") == user_id


def _bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return None


def _cache_get(token: str) -> Optional[str]:
    hit = _token_cache.get(token)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    _token_cache.pop(token, None)
    return None


def _cache_put(token: str, user_id: str) -> None:
    if len(_token_cache) >= _CACHE_MAX_ENTRIES:
        # Drop expired entries first, then the oldest if still full.
        now = time.monotonic()
        for k in [k for k, v in _token_cache.items() if v[1] <= now]:
            _token_cache.pop(k, None)
        if len(_token_cache) >= _CACHE_MAX_ENTRIES:
            _token_cache.pop(next(iter(_token_cache)), None)
    _token_cache[token] = (user_id, time.monotonic() + _CACHE_TTL_SECONDS)


async def get_current_user_id(
    request: Request, settings: Settings = Depends(get_settings)
) -> str:
    """Return the caller's user id, or raise 401 (bad token) / 503 (Auth down)."""
    if bypass_allowed(settings):
        return settings.dev_user_id

    token = _bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Please log in to continue.")

    cached = _cache_get(token)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {token}",
                },
            )
    except httpx.HTTPError:
        # Auth being unreachable must not look like "you are logged out".
        raise HTTPException(
            status_code=503,
            detail="Frank can't check your login right now. Try again in a moment.",
        )

    if res.status_code in (401, 403):
        raise HTTPException(
            status_code=401, detail="Your session has ended. Please log in again."
        )
    if res.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail="Frank can't check your login right now. Try again in a moment.",
        )

    user_id = res.json().get("id")
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Your session has ended. Please log in again."
        )
    _cache_put(token, user_id)
    return user_id


async def require_project_access(
    project_id: str, user_id: str = Depends(get_current_user_id)
) -> dict:
    """Ensure {project_id} belongs to the caller. 404 for missing OR foreign."""
    try:
        project = await projects_db.get_project(project_id=project_id)
    except APIError:
        # `.single()` raises when no row matches or the id isn't a valid UUID.
        project = None
    if not owns_project(project, user_id):
        raise HTTPException(status_code=404, detail="Song not found")
    return project
