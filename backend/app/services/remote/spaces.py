"""
Frank's remote organs (frankenstein spec 14, requirement 1.4): two Hugging Face Spaces, `frank-ears` (analysis) and
`frank-hands` (generation), called over their Gradio API.

Nothing here may fail the user's action. A Space that is asleep, building, out of GPU time or simply gone raises
`RemoteUnavailable` with a plain reason; every caller turns that into its CPU fallback or a plain sentence.

The calls hold no local audio for long: bytes go to a temp file, the file is uploaded, and the result is read back.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from typing import Any, Optional

from app.config import get_settings

log = logging.getLogger("frank.remote")

WAKE_TIMEOUT_S = 240          # a sleeping Space takes a minute or two to come back
CALL_TIMEOUT_S = 300
AVAILABLE_TTL_S = 60


class RemoteUnavailable(RuntimeError):
    """The organ could not be reached or could not do the work. `plain` is safe to show the user."""

    def __init__(self, plain: str, detail: str = "") -> None:
        super().__init__(detail or plain)
        self.plain = plain


_clients: dict[str, Any] = {}
_lock = threading.Lock()
_status: dict[str, tuple[float, bool]] = {}


def _space_id(which: str) -> str:
    s = get_settings()
    return {"ears": s.ears_space, "hands": s.hands_space}.get(which, which)


def _token() -> Optional[str]:
    s = get_settings()
    return s.spaces_token or s.hf_token or s.huggingface_api_key or None


def _client(which: str) -> Any:
    space = _space_id(which)
    with _lock:
        if space in _clients:
            return _clients[space]
    try:
        from gradio_client import Client  # imported lazily: only needed when a Space is called
    except ImportError as e:  # pragma: no cover - dependency missing
        raise RemoteUnavailable("That part of Frank isn't installed here.", str(e)) from e
    started = time.time()
    last: Exception | None = None
    while time.time() - started < WAKE_TIMEOUT_S:
        try:
            c = Client(space, hf_token=_token(), verbose=False)
            with _lock:
                _clients[space] = c
            return c
        except (TypeError, ImportError, AttributeError) as e:      # a bug, not a sleeping Space: don't wait
            raise RemoteUnavailable("That part of Frank isn't working right now.", repr(e)) from e
        except Exception as e:  # noqa: BLE001  asleep, building, network blip
            last = e
            time.sleep(8)
    raise RemoteUnavailable("Frank's helpers are waking up and didn't answer in time. Try again in a minute.", repr(last))


def call(which: str, api_name: str, *args: Any, timeout: float = CALL_TIMEOUT_S) -> Any:
    """Call one endpoint of a Space. JSON strings that come back are decoded."""
    try:
        client = _client(which)
    except RemoteUnavailable:
        _status[which] = (time.time(), False)
        raise
    result: dict[str, Any] = {}

    def run() -> None:
        try:
            result["value"] = client.predict(*args, api_name=api_name)
        except Exception as e:  # noqa: BLE001
            result["error"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise RemoteUnavailable("That took too long, so I stopped waiting. Nothing was lost.", f"{which}{api_name} timed out")
    if "error" in result:
        err = result["error"]
        text = str(err)
        log.warning("remote %s %s failed: %s", which, api_name, text[:300])
        with _lock:
            _clients.pop(_space_id(which), None)      # reconnect next time (the Space may have restarted)
        if "quota" in text.lower() or "gpu" in text.lower() and "exceed" in text.lower():
            raise RemoteUnavailable("Frank's helpers have used today's free time. This will work again tomorrow.", text)
        raise RemoteUnavailable("That helper couldn't do it this time. Want to try again?", text)
    _status[which] = (time.time(), True)
    value = result.get("value")
    if isinstance(value, str) and value[:1] in "{[":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def audio_file(data: bytes, ext: str = "wav") -> Any:
    """Bytes as an upload for a Gradio file input. The temp file is removed after the call by `cleanup`."""
    from gradio_client import handle_file

    fd, path = tempfile.mkstemp(suffix=f".{ext.lstrip('.')}", prefix="frank-")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return handle_file(path)


def cleanup(*files: Any) -> None:
    for f in files:
        path = f.get("path") if isinstance(f, dict) else getattr(f, "path", f)
        if isinstance(path, str) and os.path.basename(path).startswith("frank-"):
            try:
                os.remove(path)
            except OSError:
                pass


def read_file(result: Any) -> bytes:
    """A file returned by a Space (a path, or a dict with a path) as bytes."""
    path = result.get("path") if isinstance(result, dict) else result
    if not isinstance(path, str):
        raise RemoteUnavailable("The helper sent back nothing I could use.", repr(result))
    with open(path, "rb") as f:
        return f.read()


def available(which: str) -> bool:
    """Whether the Space answered recently (cached), for "Frank's ears are waking up" in the UI."""
    seen = _status.get(which)
    if seen and time.time() - seen[0] < AVAILABLE_TTL_S:
        return seen[1]
    try:
        call(which, "/health", timeout=30)
        return True
    except RemoteUnavailable:
        return False
