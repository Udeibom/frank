"""
Monthly allowances for outside services with small free tiers (migration 011).

Exa and Firecrawl give a few hundred calls a month. Frank spends them only when the person asks for something
(naming a song), stops before the free allowance runs out, and never pays twice for the same song
(`research_cache`). When the allowance is spent, the feature falls back to what Frank can do alone.
Caps are set below each provider's free allowance and can be changed with environment variables.
"""
from __future__ import annotations

import logging

from app.config import get_settings

log = logging.getLogger("frank.budget")


def cap_for(service: str) -> int:
    s = get_settings()
    return {"exa": s.exa_monthly_limit, "firecrawl": s.firecrawl_monthly_limit}.get(service, 0)


def spend(service: str, amount: int = 1) -> bool:
    """Use `amount` of this month's allowance. False (and nothing spent) when it would go over, or on any error:
    when in doubt, don't spend."""
    cap = cap_for(service)
    if cap <= 0:
        return False
    try:
        from app.db.client import get_supabase
        res = get_supabase().rpc("use_service", {"p_service": service, "p_cap": cap, "p_amount": amount}).execute()
        return bool(res.data)
    except Exception:  # noqa: BLE001
        log.warning("could not check the %s allowance; not spending", service, exc_info=True)
        return False
