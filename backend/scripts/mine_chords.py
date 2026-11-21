"""
How real songs move between chords (frankenstein spec 14, requirement 3.2), from Chordonomicon (666,000 songs'
chord progressions with section and genre labels; CC BY-NC 4.0).

Streams the CSV (about 260 MB) in chunks, so it runs in little memory. Per song: estimate the key from which
chords it uses, turn each chord into a scale degree, and per section count how often each of Frank's own chord
loops (theory.PROGRESSIONS) appears. The result ranks Frank's options per style, section and mode; Frank's
theory code still decides, the ranking only says which option real songs in that style use most.

  venv/bin/python scripts/mine_chords.py [CSV_URL_OR_PATH]  # writes app/services/generation/styles/chord_tables.json
"""
from __future__ import annotations

import io
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.generation.theory import PROGRESSIONS  # noqa: E402

OUT = ROOT / "app" / "services" / "generation" / "styles" / "chord_tables.json"
URL = "https://huggingface.co/datasets/ailsntua/Chordonomicon/resolve/main/chordonomicon_v2.csv"

NOTES = {"C": 0, "Cs": 1, "Db": 1, "D": 2, "Ds": 3, "Eb": 3, "E": 4, "F": 5, "Fs": 6, "Gb": 6, "G": 7, "Gs": 8, "Ab": 8,
         "A": 9, "As": 10, "Bb": 10, "B": 11, "Es": 5, "Fb": 4, "Bs": 0, "Cb": 11}
CHORD = re.compile(r"^([A-G](?:s|b)?)(min|m(?!aj)|dim)?")
SECTION = re.compile(r"<([a-z_]+?)(?:_\d+)?>")
# scale degree -> (semitones above the tonic, minor triad?) for the diatonic triads Frank uses
MAJOR = {0: (0, False), 1: (2, True), 2: (4, True), 3: (5, False), 4: (7, False), 5: (9, True)}
MINOR = {0: (0, True), 2: (3, False), 3: (5, True), 4: (7, True), 5: (8, False), 6: (10, False), 1: (2, True)}
GENRE = {"pop": "pop", "rock": "rock", "alternative": "rock", "punk": "rock", "metal": "rock", "pop rock": "rock",
         "country": "folk", "jazz": "lofi", "soul": "soul", "r&b": "soul", "rap": "hiphop", "hip hop": "hiphop",
         "electronic": "electronic", "reggae": "pop"}
KINDS = {"verse": "verse", "chorus": "chorus", "bridge": "bridge", "intro": "intro", "outro": "outro",
         "pre_chorus": "pre-chorus", "prechorus": "pre-chorus"}


def parse(chord: str):
    m = CHORD.match(chord)
    if not m or m.group(1) not in NOTES:
        return None
    return NOTES[m.group(1)], m.group(2) in ("min", "m")


def key_of(chords: list[tuple[int, bool]]) -> tuple[int, str] | None:
    """The key in which most of the song's chords are the scale's own triads; the first and last chord break ties."""
    best, score = None, -1.0
    for tonic in range(12):
        for mode, table in (("major", MAJOR), ("minor", MINOR)):
            allowed = {((tonic + st) % 12, mi) for st, mi in table.values()}
            s = sum(1 for c in chords if c in allowed) / len(chords)
            s += 0.05 * ((chords[0] == (tonic, mode == "minor")) + (chords[-1] == (tonic, mode == "minor")))
            if s > score:
                best, score = (tonic, mode), s
    return best if score >= 0.75 else None


def degree(c: tuple[int, bool], tonic: int, mode: str) -> int | None:
    table = MAJOR if mode == "major" else MINOR
    for d, (st, mi) in table.items():
        if c == ((tonic + st) % 12, mi):
            return d
    return None


def loops_in(seq: list[int]) -> Counter:
    """Every 4-chord stretch (repeats collapsed), as Frank would write it."""
    out = Counter()
    s = [d for i, d in enumerate(seq) if i == 0 or d != seq[i - 1]]
    for i in range(len(s) - 3):
        out[tuple(s[i:i + 4])] += 1
    return out


def rows(src: str):
    import csv

    if src.startswith("http"):
        with httpx.stream("GET", src, follow_redirects=True, timeout=None) as r:
            r.raise_for_status()
            lines = (l for l in r.iter_lines())
            yield from csv.DictReader(lines)
    else:
        with open(src, newline="") as f:
            yield from csv.DictReader(f)


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else URL
    candidates = {mode: [tuple(o) for fam, opts in PROGRESSIONS.items() if fam.startswith(mode) for o in opts]
                  for mode in ("major", "minor")}
    counts: dict = defaultdict(Counter)
    songs = Counter()
    n = 0
    for row in rows(src):
        n += 1
        genre = GENRE.get((row.get("main_genre") or "").strip().lower())
        tokens = (row.get("chords") or "").split()
        sections: list[tuple[str, list]] = []
        for t in tokens:
            m = SECTION.match(t)
            if m:
                sections.append((KINDS.get(m.group(1), "other"), []))
            else:
                c = parse(t)
                if c is not None:
                    if not sections:
                        sections.append(("other", []))
                    sections[-1][1].append(c)
        flat = [c for _, cs in sections for c in cs]
        if len(flat) < 8:
            continue
        key = key_of(flat)
        if key is None:
            continue
        tonic, mode = key
        cand = set(candidates[mode])
        for style in ([genre] if genre else []) + ["_default"]:
            songs[style] += 1
            for kind, cs in sections:
                if kind == "other":
                    continue
                seq = [d for d in (degree(c, tonic, mode) for c in cs) if d is not None]
                for loop, k in loops_in(seq).items():
                    if loop in cand:
                        counts[(style, kind, mode)][loop] += k
        if n % 50_000 == 0:
            print(f"{n} songs read", flush=True)
    table: dict = {"_note": "From Chordonomicon (CC BY-NC 4.0) by scripts/mine_chords.py: how often real songs use each of "
                            "Frank's chord loops, per style, section and mode.", "songs": dict(songs), "styles": {}}
    for (style, kind, mode), c in counts.items():
        total = sum(c.values()) or 1
        table["styles"].setdefault(style, {}).setdefault(kind, {})[mode] = {
            " ".join(map(str, loop)): round(v / total, 4) for loop, v in c.most_common()}
    OUT.write_text(json.dumps(table, indent=1) + "\n")
    print(f"read {n} songs; kept {songs['_default']} with a clear key; wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
