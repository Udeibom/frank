import httpx
from supabase import create_client, Client
from functools import lru_cache
from app.config import get_settings

# Supabase closes idle keep-alive connections server-side. A pooled connection
# that went stale then fails the next request with
# `httpx.RemoteProtocolError: Server disconnected` (a 500, which the browser
# reports as a CORS error). Dropping idle connections after a few seconds means
# the client never reuses one the server has already closed.
_KEEPALIVE_SECONDS = 5.0


def _with_short_keepalive(session: httpx.Client) -> httpx.Client:
    """Rebuild an httpx session with the same config but short keep-alive."""
    fresh = httpx.Client(
        base_url=session.base_url,
        headers=session.headers,
        timeout=session.timeout,
        follow_redirects=session.follow_redirects,
        limits=httpx.Limits(keepalive_expiry=_KEEPALIVE_SECONDS),
    )
    session.close()
    return fresh


@lru_cache
def get_supabase() -> Client:
    """
    Returns a singleton Supabase client using the service role key.
    The service role key bypasses Row Level Security — never expose it to the frontend.
    """
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    client.postgrest.session = _with_short_keepalive(client.postgrest.session)
    # storage3 holds the same httpx client under two names; swap both.
    storage_session = _with_short_keepalive(client.storage.session)
    client.storage.session = storage_session
    client.storage._client = storage_session
    return client
