"""
Does it sound like what was asked for? (frankenstein spec 14, requirement 2.2)

The song's direction names the styles it leans toward (fingerprint.genre_proximity: "soul", "lo-fi"). The
Discogs-EffNet labels from frank-ears say which styles the render actually sounds like. When none of the top
labels is in the same family as what was asked, the Listener says so in plain words. A label never becomes a
genre name the person sees; the finding talks about the feeling.
"""
from __future__ import annotations

from typing import Optional

from app.services.listener.models import Finding

# Frank's style words -> Discogs families and style names that count as a match (lower case).
STYLE_MATCH = {
    "soul": {"funk / soul", "soul", "neo soul", "rhythm & blues", "contemporary r&b"},
    "r&b": {"funk / soul", "contemporary r&b", "rhythm & blues", "neo soul"},
    "rnb": {"funk / soul", "contemporary r&b", "rhythm & blues"},
    "gospel": {"funk / soul", "gospel", "soul"},
    "lo-fi": {"lo-fi", "hip hop", "boom bap", "instrumental", "downtempo", "trip hop"},
    "lofi": {"lo-fi", "hip hop", "boom bap", "downtempo"},
    "hip hop": {"hip hop", "boom bap", "trap", "instrumental", "conscious"},
    "hiphop": {"hip hop", "boom bap", "trap"},
    "pop": {"pop", "synth-pop", "indie pop", "ballad", "europop", "electronic"},
    "rock": {"rock", "indie rock", "alternative rock", "pop rock", "soft rock"},
    "folk": {"folk, world, & country", "folk", "acoustic", "folk rock", "singer/songwriter"},
    "ambient": {"ambient", "electronic", "downtempo", "new age", "drone"},
    "electronic": {"electronic", "house", "techno", "synth-pop", "downtempo"},
    "jazz": {"jazz", "smooth jazz", "soul-jazz", "contemporary jazz"},
    "afrobeats": {"afrobeat", "reggae", "funk / soul", "dancehall"},
}


def matches(asked: list[str], styles: list[dict]) -> Optional[bool]:
    wanted: set[str] = set()
    for a in asked:
        wanted |= STYLE_MATCH.get(a.lower(), {a.lower()})
    if not wanted or not styles:
        return None
    for s in styles[:5]:
        if s.get("name", "").lower() in wanted or s.get("family", "").lower() in wanted:
            return True
    return False


def finding(asked: list[str], styles: list[dict], moods: list[dict]) -> Optional[Finding]:
    if matches(asked, styles) is not False:
        return None
    mood = (moods[0]["name"] if moods else "").replace("_", " ")
    feel = f" It comes across as more {mood} than you described." if mood else ""
    return Finding(id="style_drift", severity="worth_a_look", confidence=0.55, evidence=["style.labels"],
                   plain="It doesn't quite sound like the kind of song you described yet." + feel)
