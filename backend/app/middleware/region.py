"""Pure-ASGI middleware: read `X-Frank-Region` once per request into a context variable (services/region.py).
Background tasks started by the request run in the same context, so jobs inherit it."""
from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from app.services import region


class RegionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        value = None
        for k, v in scope.get("headers", []):
            if k == b"x-frank-region":
                value = v.decode("latin-1")
                break
        token = region.set_region(value)
        try:
            await self.app(scope, receive, send)
        finally:
            region._region.reset(token)
