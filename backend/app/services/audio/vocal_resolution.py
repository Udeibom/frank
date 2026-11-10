"""
Pure decision logic for which vocal the Mix Room should use.

Kept free of I/O so it can be unit- and property-tested. Rule (see
.kiro/specs/voice-to-export-flow): the most recently chosen vocal wins. Choosing
a take clears active_comp_id (done in the voice router), so by the time we get
here at most one of the two pointers is normally set. If both are set, the comp
wins, because a comp can only be active if it was chosen after the take.
"""
from typing import Optional


def resolve_vocal_url(
    active_comp: Optional[dict],
    active_take: Optional[dict],
) -> Optional[str]:
    """
    Return the audio URL the mix should use for the lead vocal, or None.

    active_comp: the comp row pointed to by active_comp_id (or None).
    active_take: the take row pointed to by active_vocal_id (or None).
    A tuned take (processed_url) is preferred over its original audio.
    """
    if active_comp and active_comp.get("audio_url"):
        return active_comp["audio_url"]
    if active_take:
        return active_take.get("processed_url") or active_take.get("audio_url")
    return None
