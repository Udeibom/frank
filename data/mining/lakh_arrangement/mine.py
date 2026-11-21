"""
How real arrangements enter and leave (frankenstein spec 14, requirement 3.3), mined on Kaggle from the Lakh MIDI
Dataset (Colin Raffel, CC BY 4.0; the "clean" subset as Kaggle dataset imsparsh/lakh-midi-clean).

For each song: which families of parts (drums, bass, keys, guitar, strings, pad, melody) play in each bar,
counted in 4/4 bars of the file's own beat. Then, for every family that plays somewhere in the song: how often it
is already there in the first 8 bars (the intro), how often it is still there in the last 8 (the ending), and how
many of the song's families the intro and ending use. Frank's intros and endings use these as priors.

A tiny MIDI reader is included, so the notebook needs no packages and no internet.
Writes arrangement_stats.json to the working directory.
"""
from __future__ import annotations

import json
import os
import struct
import sys
from collections import defaultdict

ROOTS = ["/kaggle/input/lakh-midi-clean", "/kaggle/input"] + sys.argv[1:]
EDGE_BARS = 8
MIN_BARS = 40
MAX_SONGS = 20000


def family(program: int, channel: int) -> str | None:
    if channel == 9:
        return "drums"
    if 32 <= program <= 39:
        return "bass"
    if program <= 7 or 16 <= program <= 23:
        return "keys"
    if 24 <= program <= 31:
        return "guitar"
    if 40 <= program <= 51:
        return "strings"
    if 88 <= program <= 95 or 52 <= program <= 54:
        return "pad"
    if 56 <= program <= 87:
        return "melody"
    return None


def _varlen(data: bytes, i: int) -> tuple[int, int]:
    v = 0
    while True:
        b = data[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def read(path: str) -> tuple[int, list[tuple[int, int, int]]]:
    """(ticks per beat, [(tick, channel, program)] for every note-on)."""
    data = open(path, "rb").read()
    if data[:4] != b"MThd":
        raise ValueError("not midi")
    _, ntracks, tpb = struct.unpack(">HHH", data[8:14])
    if tpb & 0x8000:
        raise ValueError("smpte timing")
    i = 14
    notes = []
    for _ in range(ntracks):
        if data[i:i + 4] != b"MTrk":
            break
        length = struct.unpack(">I", data[i + 4:i + 8])[0]
        j, end = i + 8, i + 8 + length
        tick, status = 0, 0
        programs = [0] * 16
        while j < end:
            delta, j = _varlen(data, j)
            tick += delta
            b = data[j]
            if b == 0xFF:
                j += 2
                ln, j = _varlen(data, j)
                j += ln
                continue
            if b in (0xF0, 0xF7):
                ln, j = _varlen(data, j + 1)
                j += ln
                continue
            if b & 0x80:
                status = b
                j += 1
            kind, ch = status & 0xF0, status & 0x0F
            if kind in (0xC0, 0xD0):
                if kind == 0xC0:
                    programs[ch] = data[j]
                j += 1
            else:
                a, v = data[j], data[j + 1]
                j += 2
                if kind == 0x90 and v > 0:
                    notes.append((tick, ch, programs[ch]))
        i = end
    return tpb, notes


def main() -> int:
    files = []
    for root in ROOTS:
        if os.path.isdir(root):
            for d, _, fs in os.walk(root):
                files += [os.path.join(d, f) for f in fs if f.lower().endswith((".mid", ".midi"))]
            if files:
                break
    files = sorted(files)[:MAX_SONGS]
    has = defaultdict(int)
    intro = defaultdict(int)
    ending = defaultdict(int)
    intro_share, ending_share, middle_share = [], [], []
    songs = 0
    for path in files:
        try:
            tpb, notes = read(path)
        except Exception:  # noqa: BLE001 - a broken file is skipped
            continue
        if not notes or tpb <= 0:
            continue
        bar = 4 * tpb
        last = max(t for t, _, _ in notes) // bar + 1
        if last < MIN_BARS:
            continue
        bars: dict[str, set[int]] = defaultdict(set)
        for t, ch, prog in notes:
            f = family(prog, ch)
            if f:
                bars[f].add(t // bar)
        fams = [f for f, b in bars.items() if len(b) >= 4]
        if len(fams) < 3:
            continue
        songs += 1
        start = min(min(b) for b in bars.values())
        n_in = n_out = n_mid = 0
        for f in fams:
            has[f] += 1
            b = bars[f]
            if any(start <= x < start + EDGE_BARS for x in b):
                intro[f] += 1
                n_in += 1
            if any(last - EDGE_BARS <= x < last for x in b):
                ending[f] += 1
                n_out += 1
            mid = last // 2
            if any(mid - 4 <= x < mid + 4 for x in b):
                n_mid += 1
        intro_share.append(n_in / len(fams))
        ending_share.append(n_out / len(fams))
        middle_share.append(n_mid / len(fams))
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None  # noqa: E731
    out = {
        "_note": "From the Lakh MIDI Dataset (Colin Raffel, CC BY 4.0), clean subset, by data/mining/lakh_arrangement/mine.py. "
                 "For each family of parts: the share of songs using it where it already plays in the first 8 bars and "
                 "where it still plays in the last 8.",
        "songs": songs,
        "families": {f: {"songs": has[f], "intro": round(intro[f] / has[f], 3), "ending": round(ending[f] / has[f], 3)}
                     for f in sorted(has)},
        "parts_playing": {"intro": mean(intro_share), "middle": mean(middle_share), "ending": mean(ending_share)},
    }
    with open("arrangement_stats.json", "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
