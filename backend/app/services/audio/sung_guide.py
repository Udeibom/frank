"""
A guide that sings the person's own words (frankenstein spec 14, requirement 4.2).

The song's tune (SongNotes.melody_part) gives the notes; the lyrics give the syllables, one per note, in order
(each word's CMU pronunciation split at its vowels). DiffSinger on frank-hands sings them. Extra notes hum "oo";
extra syllables are left out. It is a guide only: never mixed into a take, never presented as the person's voice.
"""
from __future__ import annotations

import re
from typing import Optional

from app.services.audio.song_notes import SongNotes
from app.services.words import sound
from app.services.words.timing import lyric_lines

VOWELS = {"aa", "ae", "ah", "ao", "aw", "ax", "ay", "eh", "er", "ey", "ih", "iy", "ow", "oy", "uh", "uw"}
WORD = re.compile(r"[A-Za-z']+")


def syllables_of(word: str) -> list[list[str]]:
    """'lullaby' -> [['l','ah'], ['l','ah'], ['b','ay']]: each vowel takes the consonants before it; trailing
    consonants stay with the last syllable."""
    p = sound.phones(word)
    if not p:
        n = sound.guess_syllables(word)
        return [["l", "ah"]] * n
    ph = [re.sub(r"\d", "", x).lower() for x in p.split()]
    out: list[list[str]] = []
    cur: list[str] = []
    for x in ph:
        cur.append(x)
        if x in VOWELS:
            out.append(cur)
            cur = []
    if cur:
        if out:
            out[-1] += cur
        else:
            out.append(cur)
    return out


def payload(song: SongNotes, lyrics: Optional[str]) -> Optional[dict]:
    if not song.melody_part or not song.sections:
        return None
    starts = {s.value[0]: s.start for s in song.sections}
    spb = song.seconds_per_beat
    notes = []
    for index, events, _ in song.melody_part:
        base = starts.get(index, 0.0) / spb
        for e in events:
            notes.append({"note": int(e.note), "start": round(base + e.start, 4), "duration": round(e.duration, 4)})
    notes.sort(key=lambda n: n["start"])
    sylls: list[list[str]] = []
    for line in lyric_lines(lyrics):
        for w in WORD.findall(line):
            sylls += syllables_of(w)
    phonemes = [sylls[i] if i < len(sylls) else ["uw"] for i in range(len(notes))]
    return {"notes": notes, "phonemes": phonemes, "bpm": song.bpm, "lead_s": 0.0}
