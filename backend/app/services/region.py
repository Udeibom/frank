"""
Where the person is, as far as the rules need to know (frankenstein spec 14, requirement 9.1).

The Gemini API terms allow only paid services when an app is offered to users in the European Economic Area,
Switzerland or the United Kingdom. Frank uses the free tier, so Gemini is never called for those requests.

The browser learns its country from Frank's own Vercel route (`/api/region`, from `x-vercel-ip-country`) and sends
it as `X-Frank-Region` on every call. A request with no region is treated as unknown, and unknown is treated as
blocked: when in doubt, don't send.
"""
from __future__ import annotations

import contextvars
from typing import Optional

# EU 27 + Iceland, Liechtenstein, Norway (EEA) + Switzerland + United Kingdom.
GEMINI_BLOCKED = frozenset(
    "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE IS LI NO CH GB".split()
)

_region: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("frank_region", default=None)


def normalise(value: Optional[str]) -> Optional[str]:
    """A two-letter country code, upper case, or None for anything else."""
    if not value:
        return None
    v = value.strip().upper()
    if v == "UK":
        v = "GB"
    return v if len(v) == 2 and v.isalpha() else None


def set_region(value: Optional[str]) -> contextvars.Token:
    return _region.set(normalise(value))


def current() -> Optional[str]:
    return _region.get()


def gemini_allowed(region: Optional[str] = None, *, explicit: bool = False) -> bool:
    """True only for a known country outside the EEA, Switzerland and the UK."""
    r = normalise(region) if explicit else (normalise(region) if region else current())
    return r is not None and r not in GEMINI_BLOCKED


GEMINI_REGION_MESSAGE = (
    "Where you are, I can't send sound or pictures to the helper that listens and looks, so I'll go by "
    "my own measurements instead."
)
