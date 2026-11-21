"""
How people describe music, measured (frankenstein spec 14, requirements 9.4 and 9.5). Runs on Kaggle (internet on).

Song Describer (Manco et al., 2023; captions CC BY-SA 4.0, recordings from MTG-Jamendo under Creative Commons):
706 recordings, 1,106 human captions. For each recording we measure what Frank's fingerprint describes: speed,
brightness, busyness and loudness. For each feeling word people used in captions, we compare the recordings they
used it for with all recordings, in standard units (z-scores). The result is a table "dreamy: darker, slower,
quieter" that calibrates how Frank turns words into a direction.

MTG-Jamendo mood check: the same recordings carry MTG-Jamendo mood tags. For every word that is also a mood tag,
we check the caption-based direction and the tag-based direction agree (requirement 9.5).

Writes feeling_words.json.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from collections import defaultdict

import numpy as np

BASE = "https://zenodo.org/api/records/10072001/files"
WORK = "/kaggle/working" if os.path.isdir("/kaggle/working") else "."
WORDS = ["dreamy", "calm", "relaxing", "peaceful", "melancholic", "sad", "dark", "happy", "upbeat", "energetic",
         "aggressive", "intense", "epic", "uplifting", "romantic", "mellow", "chill", "soft", "gentle", "warm",
         "bright", "heavy", "groovy", "funky", "driving", "atmospheric", "ambient", "haunting", "mysterious",
         "nostalgic", "emotional", "powerful", "playful", "tense", "slow", "fast", "minimal", "sparse", "busy",
         "lively", "smooth", "hopeful", "lonely", "cinematic", "spacious", "intimate", "joyful", "angry", "eerie"]
FEATURES = ["tempo", "brightness", "busyness", "loudness"]


def get(name: str, dest: str) -> str:
    path = os.path.join(WORK, dest)
    if not os.path.exists(path):
        subprocess.run(["curl", "-sL", "--retry", "5", "-C", "-", "-o", path, f"{BASE}/{name}/content"], check=True)
    return path


def features(data: bytes) -> dict | None:
    import librosa

    try:
        y, sr = librosa.load(io.BytesIO(data), sr=22050, mono=True, duration=120)
    except Exception:  # noqa: BLE001
        return None
    if y.size < sr * 10:
        return None
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    tempo = float(np.atleast_1d(librosa.beat.tempo(onset_envelope=onset, sr=sr))[0])
    while tempo > 160:
        tempo /= 2
    while tempo < 60:
        tempo *= 2
    onsets = librosa.onset.onset_detect(onset_envelope=onset, sr=sr)
    rms = librosa.feature.rms(y=y)[0]
    return {
        "tempo": tempo,
        "brightness": float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))),
        "busyness": len(onsets) / (y.size / sr),
        "loudness": float(20 * np.log10(np.mean(rms) + 1e-9)),
    }


def main() -> int:
    captions = list(csv.DictReader(open(get("song_describer.csv", "song_describer.csv"), newline="", encoding="utf-8")))
    tags_path = get("song_describer_14_04_23.mtg-jamendo.tsv", "tags.tsv")
    moods: dict[str, set[str]] = defaultdict(set)
    with open(tags_path, encoding="utf-8") as f:
        for row in f.read().splitlines():
            cols = row.split("\t")
            if len(cols) >= 6:
                track = cols[0].split("_")[-1].lstrip("0") or cols[0]
                for tag in cols[5:]:
                    if tag.startswith("mood/theme---"):
                        moods[track].add(tag.split("---")[1])
    archive = get("audio.zip", "audio.zip")
    feats: dict[str, dict] = {}
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not name.lower().endswith((".mp3", ".wav", ".ogg")):
                continue
            track = re.sub(r"\D", "", os.path.basename(name).split(".")[0]).lstrip("0")
            f = features(z.read(name))
            if f:
                feats[track] = f
            if len(feats) % 50 == 0:
                print(len(feats), "recordings measured", flush=True)
    tracks = sorted(feats)
    m = np.array([[feats[t][k] for k in FEATURES] for t in tracks])
    mean, std = m.mean(axis=0), m.std(axis=0) + 1e-9
    z = {t: (np.array([feats[t][k] for k in FEATURES]) - mean) / std for t in tracks}

    used: dict[str, set[str]] = defaultdict(set)
    for c in captions:
        track = re.sub(r"\D", "", str(c.get("track_id", ""))).lstrip("0")
        text = (c.get("caption") or "").lower()
        for w in WORDS:
            if re.search(rf"\b{w}\b", text) and track in z:
                used[w].add(track)
    table = {}
    for w, ts in used.items():
        if len(ts) < 8:
            continue
        v = np.mean([z[t] for t in ts], axis=0)
        table[w] = {"recordings": len(ts), **{k: round(float(x), 3) for k, x in zip(FEATURES, v)}}

    check = {}
    for w in table:
        tagged = [t for t in tracks if w in moods.get(t, set())]
        if len(tagged) >= 8:
            tv = np.mean([z[t] for t in tagged], axis=0)
            cv = np.array([table[w][k] for k in FEATURES])
            agree = float(np.dot(tv, cv) / (np.linalg.norm(tv) * np.linalg.norm(cv) + 1e-9))
            check[w] = {"tagged_recordings": len(tagged), "agreement": round(agree, 3)}

    out = {
        "_note": "Song Describer captions (CC BY-SA 4.0) and MTG-Jamendo recordings, by data/mining/song_describer/mine.py. "
                 "Per feeling word: how the music people described with it measures, in standard units against all "
                 "recordings (positive = faster, brighter, busier, louder). 'mood_check' compares caption words with "
                 "MTG-Jamendo mood tags on the same recordings (1 = same direction).",
        "recordings": len(tracks), "captions": len(captions), "words": table, "mood_check": check,
        "scale": {k: {"mean": round(float(a), 3), "std": round(float(b), 3)} for k, a, b in zip(FEATURES, mean, std)},
    }
    with open(os.path.join(WORK, "feeling_words.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({"words": len(table), "checked": check}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
