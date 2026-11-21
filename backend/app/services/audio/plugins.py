"""
Studio plugins (frankenstein spec 14, requirement 3.6): "Add space" uses Dragonfly's plate and room reverbs
(GPL-3.0), real studio-style rooms, loaded by pedalboard as VST3. They are installed in the Docker image
(Debian packages dragonfly-reverb-vst3, lsp-plugins-vst3). Anywhere they are missing, pedalboard's own Reverb is
used, so nothing breaks; `available()` says which one played.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

log = logging.getLogger("frank.plugins")

SEARCH = ["/usr/lib/vst3", "/usr/local/lib/vst3", os.path.expanduser("~/.vst3")]
NAMES = {"plate": "DragonflyPlateReverb.vst3", "room": "DragonflyRoomReverb.vst3"}


def _find(bundle: str) -> Optional[str]:
    for d in SEARCH:
        p = os.path.join(d, bundle)
        if os.path.exists(p):
            return p
    return None


@lru_cache(maxsize=4)
def _load(kind: str):
    path = _find(NAMES[kind])
    if not path:
        return None
    try:
        from pedalboard import load_plugin

        return load_plugin(path)
    except Exception:  # noqa: BLE001
        log.warning("could not load %s", path, exc_info=True)
        return None


def available() -> dict[str, bool]:
    return {k: _find(v) is not None for k, v in NAMES.items()}


def _set(plugin, **values) -> None:
    """Set parameters by their plain names when the plugin has them (names differ a little between versions)."""
    params = {k.lower().replace(" ", "_"): k for k in plugin.parameters.keys()}
    for want, v in values.items():
        key = next((params[k] for k in params if want in k), None)
        if key is not None:
            try:
                setattr(plugin, key, v)
            except Exception:  # noqa: BLE001
                pass


def space(kind: str = "plate", amount: float = 0.2):
    """A fresh reverb plugin for one render, or None (the caller then uses pedalboard's Reverb).
    amount 0..1 is how much space; the dry sound always stays at full level."""
    plugin = _load(kind)
    if plugin is None:
        return None
    _set(plugin, dry_level=100.0, wet_level=max(5.0, min(60.0, amount * 100.0)), decay=1.6 if kind == "plate" else 1.2,
         predelay=12.0, width=100.0)
    return plugin
