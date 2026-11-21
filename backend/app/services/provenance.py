"""
Where each piece of help came from (frankenstein spec 14, requirement 1.3).

Every organ that shaped a version records one plain line ("Drums: from a real drummer's groove") and, when its
licence asks for it, an attribution. The change line shows the plain line; the Finish room lists them all as the
song's credits. Recording never fails the job that made the music.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.services.team.plain import find_jargon

log = logging.getLogger("frank.provenance")

# Each organ: the plain line Frank shows, and the attribution its licence asks for (None when none is needed).
ORGANS: dict[str, tuple[str, Optional[str]]] = {
    "groove": ("Drums: the feel comes from real drummers' playing", "Groove MIDI Dataset, Google Magenta (CC BY 4.0)"),
    "chords": ("Chords: shaped by how real songs in this style move", "Chordonomicon (CC BY-NC 4.0)"),
    "arrangement": ("Arrangement: which parts play where follows real songs", "Lakh MIDI Dataset (CC BY 4.0)"),
    "samples": ("Piano and strings: recorded instruments", "Versilian Studios VSCO-2 CE and VCSL (CC0)"),
    "plugins": ("Space and polish: studio room and plate effects", "Dragonfly Reverb (GPL-3.0), LSP Plugins (LGPL-3.0)"),
    "accompaniment": ("New part: written around your tune", "Anticipatory Music Transformer, Stanford CRFM (Apache-2.0)"),
    "timbre": ("Your hum, played as an instrument", "DDSP, Google Magenta (Apache-2.0)"),
    "singer": ("Guide voice: sings your words so you can hear how the line goes", "DiffSinger / OpenVPI voicebank"),
    "quiet": ("Your take, with the background noise taken out", "DeepFilterNet (MIT / Apache-2.0)"),
    "atmosphere_freesound": ("Atmosphere: a real recorded sound", None),
    "atmosphere_generated": ("Atmosphere: made from your words", "Stable Audio 3 Small, Stability AI (Community Licence)"),
    "reference_master": ("Finish: matched to the song you picked", "Matchering 2 (GPL-3.0)"),
    "reference_mix": ("Balance: settings worked out from the song you picked", "Diff-MST (research code)"),
    "reference": ("Reference: a song you pointed at, listened to for its feeling", None),
    "listened": ("Frank listened to the mix before suggesting this", "Google Gemini"),
    "looked": ("Feeling: taken from the picture you shared", "Google Gemini"),
    "moment": ("Feeling: taken from your time and weather right now", "Open-Meteo (CC BY 4.0)"),
    "words_sound": ("Words: syllables and rhymes from a pronouncing dictionary", "CMU Pronouncing Dictionary (BSD)"),
    "rhymes": ("Words: rhymes suggested by Datamuse", "Datamuse API"),
    "emotion": ("Song shape: follows the feelings in your words", "GoEmotions model (MIT)"),
    "recognised": ("Directions: matched to the words you used", "LAION CLAP (Apache-2.0)"),
    "style": ("Checked: does it sound like the style you asked for", "Essentia Discogs-EffNet, MTG-UPF (CC BY-NC-SA 4.0)"),
    "aesthetics": ("Checked: did the change make it sound better made", "Meta Audiobox Aesthetics (CC BY 4.0)"),
    "voice": ("Frank read this note aloud", "Kokoro-82M (Apache-2.0)"),
}


@dataclass(frozen=True)
class Line:
    organ: str
    plain: str
    attribution: Optional[str]


def line_for(organ: str, plain: Optional[str] = None, attribution: Optional[str] = None) -> Line:
    """The provenance line for an organ. Custom plain text must still be jargon-free; if not, the default is used."""
    default_plain, default_attr = ORGANS.get(organ, ("Help from one of Frank's tools", None))
    text = plain if plain and not find_jargon(plain) else default_plain
    return Line(organ, text, attribution if attribution is not None else default_attr)


def note(project_id: str, layer: str, version_id: Optional[str], organ: str,
         plain: Optional[str] = None, attribution: Optional[str] = None) -> Optional[Line]:
    """Record one line. Sync (call from worker threads). Returns the line, or None if it could not be stored."""
    line = line_for(organ, plain, attribution)
    try:
        from app.db.client import get_supabase

        get_supabase().table("provenance").insert({
            "project_id": project_id, "layer": layer, "version_id": version_id,
            "organ": line.organ, "plain": line.plain, "attribution": line.attribution,
        }).execute()
        return line
    except Exception:  # noqa: BLE001 - credits are never worth failing the music for
        log.warning("could not record provenance for %s", organ, exc_info=True)
        return None


def for_project(project_id: str) -> list[dict]:
    from app.db.client import get_supabase

    rows = (get_supabase().table("provenance").select("layer,version_id,organ,plain,attribution,created_at")
            .eq("project_id", project_id).order("created_at").execute().data) or []
    return rows


def credits(rows: list[dict]) -> list[dict]:
    """One credit per organ (the first time it helped), in the order they first helped."""
    seen: dict[str, dict] = {}
    for r in rows:
        key = r["organ"] + "|" + (r.get("attribution") or "")
        if key not in seen:
            seen[key] = {"organ": r["organ"], "plain": r["plain"], "attribution": r.get("attribution"), "layer": r["layer"]}
    return list(seen.values())
