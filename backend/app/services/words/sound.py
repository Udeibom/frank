"""
How words sound (frankenstein spec 14, requirement 5.1): syllables, stress and rhyme from the CMU Pronouncing
Dictionary, offline. Datamuse (requirement 5.2) adds near rhymes when it can be reached.

What the person sees is plain: "8 beats", the strong syllables marked, and lines that rhyme sharing a colour.
Words the dictionary does not know get a syllable estimate from their vowels, marked as a guess.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import httpx

from app.config import get_settings

log = logging.getLogger("frank.words")

WORD = re.compile(r"[A-Za-z']+")
VOWELS = re.compile(r"[aeiouy]+")


DB = Path(__file__).resolve().parents[3] / "assets" / "words.sqlite"


@lru_cache(maxsize=1)
def _db() -> Optional[sqlite3.Connection]:
    """The dictionary on disk (scripts/build_words_db.py). None if it was never built: then every word is guessed."""
    if not DB.exists():
        log.warning("words.sqlite missing; syllables will be estimated")
        return None
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True, check_same_thread=False)


def stresses(p: str) -> str:
    return "".join(ch for ch in p if ch.isdigit())


def rhyming_part(p: str) -> str:
    """From the last strongly stressed vowel to the end ("N AY1 T" -> "AY1 T"); the last vowel if none is strong."""
    ph = p.split()
    for i in range(len(ph) - 1, -1, -1):
        if ph[i][-1] in "12":
            return " ".join(ph[i:])
    for i in range(len(ph) - 1, -1, -1):
        if ph[i][-1].isdigit():
            return " ".join(ph[i:])
    return p


def phones(word: str) -> Optional[str]:
    db = _db()
    if db is None:
        return None
    row = db.execute("SELECT phones FROM words WHERE word = ? ORDER BY rank LIMIT 1", (word.lower().strip("'"),)).fetchone()
    return row[0] if row else None


def _rhyming_words(rhyme: str, exclude: str, limit: int) -> list[str]:
    db = _db()
    if db is None:
        return []
    rows = db.execute("SELECT DISTINCT word FROM words WHERE rhyme = ? AND word != ? AND rank = 0 AND word NOT LIKE '%''%' "
                      "ORDER BY length(word), word LIMIT ?", (rhyme, exclude, limit)).fetchall()
    return [r[0] for r in rows]


def guess_syllables(word: str) -> int:
    w = word.lower()
    n = len(VOWELS.findall(w))
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and n > 1:
        n -= 1
    return max(1, n)


@dataclass
class WordSound:
    text: str
    syllables: int
    stresses: str               # one digit per syllable: 1 strong, 2 medium, 0 weak
    rhyme: Optional[str]        # the sound from the last strong vowel to the end, e.g. "EY1 T"
    known: bool


def word_sound(word: str) -> WordSound:
    p = phones(word)
    if p is None:
        n = guess_syllables(word)
        return WordSound(word, n, "1" + "0" * (n - 1) if n > 1 else "1", None, False)
    st = stresses(p)
    return WordSound(word, len(st), st, rhyming_part(p), True)


@dataclass
class LineSound:
    text: str
    syllables: int
    words: list[WordSound] = field(default_factory=list)
    end_rhyme: Optional[str] = None
    rhyme_group: Optional[int] = None    # lines with the same number rhyme with each other
    guessed: bool = False


def _vowel_core(rhyme: Optional[str]) -> Optional[str]:
    """The vowel sound alone (stress removed), for near rhymes: 'time' and 'mine' share 'AY'."""
    if not rhyme:
        return None
    return re.sub(r"\d", "", rhyme.split()[0])


def analyse_line(text: str) -> LineSound:
    words = [word_sound(w) for w in WORD.findall(text)]
    last = next((w for w in reversed(words) if w.syllables > 0), None)
    return LineSound(text, sum(w.syllables for w in words), words, last.rhyme if last else None,
                     guessed=any(not w.known for w in words))


def group_rhymes(lines: list[LineSound]) -> None:
    """Exact end rhymes share a group; failing that, lines whose last strong vowel matches (near rhymes) share one."""
    groups: dict[str, int] = {}
    counts: dict[str, int] = {}
    for l in lines:
        if l.end_rhyme:
            counts[l.end_rhyme] = counts.get(l.end_rhyme, 0) + 1
    next_id = 0
    for l in lines:
        if l.end_rhyme and counts[l.end_rhyme] > 1:
            if l.end_rhyme not in groups:
                groups[l.end_rhyme] = next_id
                next_id += 1
            l.rhyme_group = groups[l.end_rhyme]
    # near rhymes: only where two or more otherwise unrhymed lines share a vowel core
    pending: dict[str, list[LineSound]] = {}
    for l in lines:
        if l.rhyme_group is None and l.end_rhyme:
            pending.setdefault(_vowel_core(l.end_rhyme) or "", []).append(l)
    for core, ls in pending.items():
        if core and len(ls) > 1:
            for l in ls:
                l.rhyme_group = next_id
            next_id += 1


def analyse(lyrics: str) -> list[LineSound]:
    from app.services.words.timing import lyric_lines

    lines = [analyse_line(t) for t in lyric_lines(lyrics)]
    group_rhymes(lines)
    return lines


def plain_notes(lines: list[LineSound]) -> list[str]:
    """At most two plain observations, the kind a co-writer would make. Never a rule, always an observation."""
    notes: list[str] = []
    for a, b in zip(lines, lines[1:]):
        if a.syllables and b.syllables and abs(a.syllables - b.syllables) >= 4:
            longer, shorter = (a, b) if a.syllables > b.syllables else (b, a)
            notes.append(f'"{longer.text[:40]}" has {longer.syllables - shorter.syllables} more beats than the line next '
                         f"to it, so it will feel rushed or stretched when sung. Want a shorter way to say it?")
            break
    unrhymed = [l for l in lines if l.rhyme_group is None and l.end_rhyme]
    if lines and len(unrhymed) == len(lines) and len(lines) >= 4:
        notes.append("None of the lines rhyme yet. That can be lovely and loose, or I can find a few rhymes if you'd like them.")
    return notes[:2]


def rhymes(word: str, limit: int = 12) -> dict:
    """Exact rhymes from the dictionary, near rhymes and sound-alikes from Datamuse when reachable."""
    p = phones(word)
    exact = _rhyming_words(rhyming_part(p), word.lower(), limit) if p else []
    out: dict = {"word": word, "rhymes": exact, "near": [], "sounds_like": [], "source": "dictionary"}
    params_key = get_settings().datamuse_api_key
    try:
        base = {"max": limit}
        if params_key:
            base["key"] = params_key
        near = httpx.get("https://api.datamuse.com/words", params={**base, "rel_nry": word}, timeout=6.0).json()
        like = httpx.get("https://api.datamuse.com/words", params={**base, "sl": word}, timeout=6.0).json()
        ranked = httpx.get("https://api.datamuse.com/words", params={**base, "rel_rhy": word}, timeout=6.0).json()
        if ranked:                                     # Datamuse ranks by how common the word is; prefer that order
            out["rhymes"] = [w["word"] for w in ranked if " " not in w["word"]][:limit]
        out["near"] = [w["word"] for w in near if w["word"] not in out["rhymes"]][:limit]
        out["sounds_like"] = [w["word"] for w in like if w["word"].lower() != word.lower()][:limit]
        out["source"] = "dictionary+datamuse"
    except Exception:  # noqa: BLE001 - offline: the dictionary answer stands
        log.info("datamuse unreachable; dictionary rhymes only")
    return out


def as_json(lines: list[LineSound]) -> list[dict]:
    return [{"text": l.text, "syllables": l.syllables, "rhyme_group": l.rhyme_group, "guessed": l.guessed,
             "words": [{"text": w.text, "syllables": w.syllables, "stresses": w.stresses} for w in l.words]}
            for l in lines]
