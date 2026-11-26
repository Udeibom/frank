"""
Mine real drummers' feel and full one-bar patterns from the Groove MIDI Dataset (Magenta, CC BY 4.0) into
the small table the engine reads (frankenstein spec 14, requirement 3.1).

  venv/bin/python scripts/mine_grooves.py ~/frank-data/groove

The result keeps the old per-step offset/spread/accent table and adds version 2 full patterns. Frank's
typed patterns remain the fallback; the mined patterns decide which hits a natural groove plays.
"""
from __future__ import annotations

import csv
import json
import pathlib
import statistics
import sys
from collections import defaultdict

import mido

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "services" / "generation" / "styles" / "grooves.json"

LANE_OF = {36: "kick", 38: "snare", 40: "snare", 37: "snare", 42: "hat", 22: "hat", 44: "hat", 46: "open", 26: "open"}
LANES = ("kick", "snare", "hat", "open", "ghost")
GHOST_VEL = 45
FAMILY = {
    "soul": ["soul", "gospel", "lofi"], "funk": ["soul", "hiphop"], "hiphop": ["hiphop", "lofi"], "gospel": ["gospel"],
    "pop": ["pop", "electronic"], "rock": ["rock"], "punk": ["rock"], "country": ["folk"], "blues": ["folk", "soul"],
    "jazz": ["lofi"], "reggae": ["pop"], "afrobeat": ["hiphop", "pop"], "latin": ["pop"], "dance": ["electronic"],
    "neworleans": ["soul"], "highlife": ["pop"], "afrocuban": ["pop"], "middleeastern": [],
}
MIN_HITS = 12
MIN_PATTERN_RATE = 0.08


def hits(path: pathlib.Path) -> list[tuple[str, int, float, int]]:
    mid = mido.MidiFile(str(path))
    tpb = mid.ticks_per_beat
    out = []
    t = 0
    for msg in mido.merge_tracks(mid.tracks):
        t += msg.time
        if msg.type != "note_on" or msg.velocity == 0 or msg.note not in LANE_OF:
            continue
        steps = (t / tpb) * 4.0
        nearest = round(steps)
        lane = LANE_OF[msg.note]
        if lane == "snare" and msg.velocity < GHOST_VEL:
            lane = "ghost"
        out.append((lane, int(nearest) % 16, steps - nearest, msg.velocity))
    return out


def _pattern(presence: dict[str, dict[int, int]], recordings: int) -> dict[str, str]:
    out: dict[str, str] = {}
    for lane in LANES:
        row = presence.get(lane) or {}
        chars = []
        for step in range(16):
            rate = row.get(step, 0) / max(1, recordings)
            chars.append("." if rate < MIN_PATTERN_RATE else ("o" if lane == "open" else "g" if lane == "ghost" else "x"))
        out[lane] = "".join(chars)
    return out


def main() -> int:
    root = pathlib.Path(sys.argv[1]).expanduser()
    acc: dict[str, dict[str, dict[int, list[tuple[float, int]]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    presence: dict[str, dict[str, dict[int, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    files = defaultdict(int)
    with open(root / "info.csv") as f:
        for row in csv.DictReader(f):
            if row["beat_type"] != "beat" or row["time_signature"] != "4-4":
                continue
            fam = row["style"].split("/")[0]
            targets = FAMILY.get(fam, []) + ["_default"]
            found = hits(root / row["midi_filename"])
            for style in targets:
                files[style] += 1
                seen: set[tuple[str, int]] = set()
                for lane, step, off, vel in found:
                    acc[style][lane][step].append((off, vel))
                    if (lane, step) not in seen:
                        seen.add((lane, step))
                        presence[style][lane][step] += 1
    table: dict = {"version": 2,
                   "_note": "Mined from the Groove MIDI Dataset (Google Magenta, CC BY 4.0) by scripts/mine_grooves.py. "
                            "offset/spread in sixteenth steps, accent relative to the lane's mean velocity. "
                            "patterns are one-bar lane strings: x hit, o open, g ghost, . rest.",
                   "styles": {}}
    for style, lanes in acc.items():
        out_lanes = {}
        for lane, steps in lanes.items():
            mean_vel = statistics.mean(v for hs in steps.values() for _, v in hs) or 1
            row = {"offset": [0.0] * 16, "spread": [0.0] * 16, "accent": [1.0] * 16}
            for s in range(16):
                hs = steps.get(s, [])
                if len(hs) >= MIN_HITS:
                    offs = [o for o, _ in hs]
                    row["offset"][s] = round(statistics.mean(offs), 4)
                    row["spread"][s] = round(statistics.pstdev(offs), 4)
                    row["accent"][s] = round(statistics.mean(v for _, v in hs) / mean_vel, 3)
            out_lanes[lane] = row
        table["styles"][style] = {"recordings": files[style], "lanes": out_lanes,
                                  "patterns": {"natural": {"all": _pattern(presence[style], files[style])}}}
    OUT.write_text(json.dumps(table, indent=1) + "\n")
    for style, d in sorted(table["styles"].items()):
        print(f"{style:12} {d['recordings']:4} recordings; kick {d['patterns']['natural']['all']['kick']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
