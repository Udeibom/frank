"""
Mine real drummers' feel from the Groove MIDI Dataset (Magenta, CC BY 4.0) into a small table the engine uses
(frankenstein spec 14, requirement 3.1).

For every 4/4 beat recording, each hit is placed on its nearest sixteenth step in the bar. Per style family,
lane (kick, snare, hat, open hat, ghost) and step we keep:
  offset   mean distance from the grid, in steps (negative = early, positive = late)
  spread   how much that distance varies between hits (a drummer's looseness)
  accent   mean velocity relative to that lane's mean (1.0 = average)
Frank's typed patterns still decide WHICH hits play; this only decides HOW each is played.

  venv/bin/python scripts/mine_grooves.py ~/frank-data/groove     # writes app/services/generation/styles/grooves.json
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

# Roland TD-11 note numbers in GMD -> Frank's lanes
LANE_OF = {36: "kick", 38: "snare", 40: "snare", 37: "snare", 42: "hat", 22: "hat", 44: "hat", 46: "open", 26: "open"}
GHOST_VEL = 45                     # a snare hit this soft is a ghost note
# GMD style (first part of "funk/groove1") -> Frank's styles that take it
FAMILY = {
    "soul": ["soul", "gospel", "lofi"], "funk": ["soul", "hiphop"], "hiphop": ["hiphop", "lofi"], "gospel": ["gospel"],
    "pop": ["pop", "electronic"], "rock": ["rock"], "punk": ["rock"], "country": ["folk"], "blues": ["folk", "soul"],
    "jazz": ["lofi"], "reggae": ["pop"], "afrobeat": ["hiphop", "pop"], "latin": ["pop"], "dance": ["electronic"],
    "neworleans": ["soul"], "highlife": ["pop"], "afrocuban": ["pop"], "middleeastern": [],
}
MIN_HITS = 12


def hits(path: pathlib.Path, bpm: float) -> list[tuple[str, int, float, int]]:
    """(lane, step 0..15, offset in steps, velocity) for every hit, using the file's own tempo map."""
    mid = mido.MidiFile(str(path))
    tpb = mid.ticks_per_beat
    out = []
    t = 0
    for msg in mido.merge_tracks(mid.tracks):
        t += msg.time
        if msg.type != "note_on" or msg.velocity == 0 or msg.note not in LANE_OF:
            continue
        beats = t / tpb
        steps = beats * 4.0
        nearest = round(steps)
        lane = LANE_OF[msg.note]
        if lane == "snare" and msg.velocity < GHOST_VEL:
            lane = "ghost"
        out.append((lane, int(nearest) % 16, steps - nearest, msg.velocity))
    return out


def main() -> int:
    root = pathlib.Path(sys.argv[1]).expanduser()
    acc: dict[str, dict[str, dict[int, list[tuple[float, int]]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    files = defaultdict(int)
    with open(root / "info.csv") as f:
        for row in csv.DictReader(f):
            if row["beat_type"] != "beat" or row["time_signature"] != "4-4":
                continue
            fam = row["style"].split("/")[0]
            targets = FAMILY.get(fam, []) + ["_default"]
            got = hits(root / row["midi_filename"], float(row["bpm"]))
            for style in targets:
                files[style] += 1
                for lane, step, off, vel in got:
                    acc[style][lane][step].append((off, vel))
    table: dict = {"_note": "Mined from the Groove MIDI Dataset (Google Magenta, CC BY 4.0) by scripts/mine_grooves.py. "
                            "offset/spread in sixteenth steps, accent relative to the lane's mean velocity.",
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
        table["styles"][style] = {"recordings": files[style], "lanes": out_lanes}
    OUT.write_text(json.dumps(table, indent=1) + "\n")
    for style, d in sorted(table["styles"].items()):
        h = d["lanes"].get("hat", {})
        print(f"{style:12} {d['recordings']:4} recordings; hat offsets {h.get('offset', [])[:4]} accents {h.get('accent', [])[:4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
