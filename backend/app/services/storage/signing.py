"""
Private-audio support (see .kiro/specs/private-audio).

All storage buckets are private. The URL strings saved in the database are
treated as permanent *references* to one file (bucket + path). They are turned
into short-lived signed links on the way out (sign_json, used by the response
middleware), and read directly with the service role on the backend
(fetch_audio_bytes, used by background jobs).

parse_storage_url and sign_json are pure (no I/O); the network signer is passed
in, so the rewrite logic can be property-tested.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Iterable
from urllib.parse import unquote, urlsplit

import httpx

from app.config import get_settings
from app.db.client import get_supabase

Ref = tuple[str, str]  # (bucket, path)
Signer = Callable[[set[Ref]], dict[Ref, str]]

_OBJECT_PATH = re.compile(r"^/storage/v1/object/(?:public|sign|authenticated)/([^/]+)/(.+)$")

SIGNED_URL_TTL_SECONDS = 2 * 60 * 60      # how long a handed-out link works
_CACHE_REUSE_SECONDS = 60 * 60            # reuse a link for up to this long
_CACHE_MAX_ENTRIES = 2000
_signed_cache: dict[Ref, tuple[str, float]] = {}


# ── Pure helpers ─────────────────────────────────────────────────

def parse_storage_url(value: Any, supabase_url: str) -> Ref | None:
    """
    If `value` is entirely one of OUR storage URLs, return (bucket, path);
    otherwise None. Only the whole string counts; prose that merely mentions a
    URL is never matched.
    """
    if not isinstance(value, str) or not value.startswith(("http://", "https://")):
        return None
    ours = urlsplit(supabase_url)
    parts = urlsplit(value)
    if (parts.scheme, parts.netloc) != (ours.scheme, ours.netloc):
        return None
    match = _OBJECT_PATH.match(parts.path)
    if not match:
        return None
    return match.group(1), unquote(match.group(2))


def _collect(obj: Any, supabase_url: str, found: set[Ref]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _collect(v, supabase_url, found)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, supabase_url, found)
    else:
        ref = parse_storage_url(obj, supabase_url)
        if ref:
            found.add(ref)


def _replace(obj: Any, supabase_url: str, signed: dict[Ref, str]) -> Any:
    if isinstance(obj, dict):
        return {k: _replace(v, supabase_url, signed) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace(v, supabase_url, signed) for v in obj]
    ref = parse_storage_url(obj, supabase_url)
    if ref and ref in signed:
        return signed[ref]
    return obj


def sign_json(obj: Any, supabase_url: str, signer: Signer) -> Any:
    """
    Return `obj` with every value that is a whole Frank storage URL replaced by
    the signed URL `signer` provides. Everything else, including the shape of
    the data, is unchanged. If the signer fails or omits a file, that value is
    left as it was.
    """
    found: set[Ref] = set()
    _collect(obj, supabase_url, found)
    if not found:
        return obj
    try:
        signed = signer(found)
    except Exception:  # noqa: BLE001 — never turn a signing problem into a 500
        return obj
    return _replace(obj, supabase_url, signed)


# ── Network signer (cached) ──────────────────────────────────────

def _evict_if_full(now: float) -> None:
    if len(_signed_cache) < _CACHE_MAX_ENTRIES:
        return
    for k in [k for k, v in _signed_cache.items() if v[1] <= now]:
        _signed_cache.pop(k, None)
    while len(_signed_cache) >= _CACHE_MAX_ENTRIES:
        _signed_cache.pop(next(iter(_signed_cache)))


def supabase_signer(refs: set[Ref]) -> dict[Ref, str]:
    """Sign files in one batch call per bucket, reusing recent links."""
    now = time.monotonic()
    out: dict[Ref, str] = {}
    missing: dict[str, list[str]] = {}

    for ref in refs:
        hit = _signed_cache.get(ref)
        if hit and hit[1] > now:
            out[ref] = hit[0]
        else:
            missing.setdefault(ref[0], []).append(ref[1])

    sb = get_supabase()
    for bucket, paths in missing.items():
        results = sb.storage.from_(bucket).create_signed_urls(
            paths, SIGNED_URL_TTL_SECONDS
        )
        for item in results:
            url, path = item.get("signedURL"), item.get("path")
            if url and path and not item.get("error"):
                _evict_if_full(now)
                _signed_cache[(bucket, path)] = (url, now + _CACHE_REUSE_SECONDS)
                out[(bucket, path)] = url
    return out


def sign_response_json(obj: Any) -> Any:
    """sign_json wired to this deployment's Supabase project."""
    return sign_json(obj, get_settings().supabase_url, supabase_signer)


# ── Backend reads ────────────────────────────────────────────────

def fetch_audio_bytes(url: str, timeout: float = 60.0) -> bytes:
    """
    Read a stored audio file for a background job. Frank storage URLs are read
    through the storage API with the service role (works whatever the bucket's
    visibility); any other URL is fetched over HTTP.
    """
    ref = parse_storage_url(url, get_settings().supabase_url)
    if ref:
        bucket, path = ref
        return get_supabase().storage.from_(bucket).download(path)
    resp = httpx.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content
