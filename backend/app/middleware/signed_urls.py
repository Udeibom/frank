"""
Pure-ASGI middleware: in every JSON response, swap Frank storage URLs for
short-lived signed URLs (see .kiro/specs/private-audio).

Doing it here, once, means no endpoint has to remember to sign its URLs. It is
plain ASGI rather than BaseHTTPMiddleware to avoid that class's body-buffering
and background-task quirks. Non-JSON responses (and JSON with no storage URL)
pass through untouched.
"""
from __future__ import annotations

import asyncio
import json
import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.storage.signing import sign_response_json

log = logging.getLogger("frank.signed_urls")
_MARKER = b"/storage/v1/object/"


def _is_json(headers: list[tuple[bytes, bytes]]) -> bool:
    for k, v in headers:
        if k.lower() == b"content-type":
            return v.lower().startswith(b"application/json")
    return False


async def _rewrite(body: bytes) -> bytes:
    """Return the body with storage URLs signed; the original on any problem."""
    if _MARKER not in body:
        return body
    try:
        data = json.loads(body)
        # Signing makes network calls; keep them off the event loop.
        signed = await asyncio.to_thread(sign_response_json, data)
        return json.dumps(signed, separators=(",", ":")).encode()
    except Exception:  # noqa: BLE001
        log.exception("could not sign storage URLs; returning response unchanged")
        return body


class SignedUrlMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start: Message | None = None
        json_response = False
        chunks: list[bytes] = []

        async def send_wrapper(message: Message) -> None:
            nonlocal start, json_response
            if message["type"] == "http.response.start":
                json_response = _is_json(message.get("headers", []))
                if json_response:
                    start = message  # hold until we know the final body length
                else:
                    await send(message)
                return

            if message["type"] == "http.response.body" and json_response:
                chunks.append(message.get("body", b""))
                if message.get("more_body", False):
                    return
                body = await _rewrite(b"".join(chunks))
                assert start is not None
                headers = [
                    (k, v) for k, v in start["headers"] if k.lower() != b"content-length"
                ]
                headers.append((b"content-length", str(len(body)).encode()))
                await send({**start, "headers": headers})
                await send({"type": "http.response.body", "body": body})
                return

            await send(message)

        await self.app(scope, receive, send_wrapper)
