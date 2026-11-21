"""
DiffSinger guide voice (frankenstein spec 14, requirement 4.2) with the Tiger English voicebank (spicytigermeat,
CC BY-NC-ND 4.0 + Commons Clause: free for non-commercial use; downloaded from its official release, never
redistributed or modified).

A small renderer, not OpenUtau: words become phonemes (the voicebank's own dictionary, else the CMU dictionary),
consonants are placed just before each note and the vowel holds the note, the pitch follows the tune with a short
glide, then the voicebank's acoustic model makes the sound and its vocoder turns it into audio. It is a guide, so
the person hears how the line goes before singing it themselves.
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import urllib.request
import zipfile
from functools import lru_cache
from pathlib import Path

import numpy as np

PACK = "https://github.com/spicytigermeat/tiger_diffsinger/releases/download/v106/TIGER_DS_v106_PACK.zip"
CONSONANT_S = 0.07


def _yaml(path: str) -> dict:
    import yaml

    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)      # the C parser: the dictionaries are large
    with open(path, encoding="utf-8") as f:
        return yaml.load(f, Loader=loader) or {}


_vb_lock = __import__("threading").Lock()


def voicebank(cache: str) -> Path:
    """Download and unpack the voicebank once per Space start (to disk, never whole in memory)."""
    root = Path(cache) / "tiger"
    with _vb_lock:
        found = [p for p in root.rglob("dsconfig.yaml") if p.parent.name not in ("dsdur", "dspitch", "dsvariance", "dsacoustic")]
        if not found:
            root.mkdir(parents=True, exist_ok=True)
            pack = root / "pack.zip"
            if not pack.exists():
                tmp = root / "pack.part"
                urllib.request.urlretrieve(PACK, tmp)
                tmp.replace(pack)
            inner_path = root / "inner.zip"
            with zipfile.ZipFile(pack) as outer:
                inner_name = next(n for n in outer.namelist() if n.endswith(".zip"))
                with outer.open(inner_name) as src, open(inner_path, "wb") as dst:
                    import shutil

                    shutil.copyfileobj(src, dst, 1 << 20)
            with zipfile.ZipFile(inner_path) as inner:
                inner.extractall(root / "vb")
            pack.unlink(missing_ok=True)
            inner_path.unlink(missing_ok=True)
            found = [p for p in root.rglob("dsconfig.yaml") if p.parent.name not in ("dsdur", "dspitch", "dsvariance", "dsacoustic")]
    return found[0].parent


def warm(cache: str) -> None:
    try:
        voicebank(cache)
        _models(cache)
        _dictionary(cache)
    except Exception as e:  # noqa: BLE001
        print("voicebank warm-up failed:", e, flush=True)


def layout(cache: str) -> dict:
    """What the voicebank holds (for debugging on the Space)."""
    vb = voicebank(cache)
    files = sorted(str(p.relative_to(vb)) for p in vb.rglob("*") if p.is_file())
    return {"root": str(vb), "files": files[:200], "dsconfig": _yaml(str(vb / "dsconfig.yaml"))}


@lru_cache(maxsize=1)
def _models(cache: str):
    import onnxruntime as ort

    vb = voicebank(cache)
    cfg = _yaml(str(vb / "dsconfig.yaml"))
    acoustic = ort.InferenceSession(str(vb / cfg["acoustic"]), providers=["CPUExecutionProvider"])
    voc_ref = cfg.get("vocoder")
    voc_path = None
    for cand in glob.glob(str(vb / "**" / "*.onnx"), recursive=True):
        if "vocoder" in cand.lower() or (voc_ref and voc_ref.lower() in cand.lower()):
            if cand != str(vb / cfg["acoustic"]):
                voc_path = cand
    if voc_path is None:
        voc_path = _fetch_vocoder(cache, voc_ref)
    vocoder = ort.InferenceSession(voc_path, providers=["CPUExecutionProvider"])
    phonemes_file = vb / cfg["phonemes"]
    if phonemes_file.suffix == ".json":
        table = json.loads(phonemes_file.read_text(encoding="utf-8"))
    else:
        table = {p.strip(): i for i, p in enumerate(phonemes_file.read_text(encoding="utf-8").splitlines()) if p.strip()}
    return cfg, acoustic, vocoder, table, vb


def _fetch_vocoder(cache: str, name: str | None) -> str:
    """OpenUtau's shared NSF-HiFiGAN vocoder (OpenVPI, CC BY-NC-SA 4.0) when the voicebank does not include one."""
    d = Path(cache) / "vocoder"
    d.mkdir(parents=True, exist_ok=True)
    onnx = list(d.rglob("*.onnx"))
    if onnx:
        return str(onnx[0])
    url = "https://github.com/openvpi/vocoders/releases/download/pc-nsf-hifigan-44.1k-hop512-128bin-2025.02/pc_nsf_hifigan_44.1k_hop512_128bin_2025.02.oudep"
    zp = d / "voc.zip"
    urllib.request.urlretrieve(url, zp)
    with zipfile.ZipFile(zp) as z:
        z.extractall(d)
    return str(next(d.rglob("*.onnx")))


@lru_cache(maxsize=1)
def _dictionary(cache: str) -> dict:
    vb = voicebank(cache)
    out: dict = {}
    english = sorted(vb.rglob("dsdict-en.yaml")) or sorted(vb.rglob("dsdict.yaml"))
    for p in english[:1]:                      # English only: the other languages' dictionaries are not needed
        d = _yaml(str(p))
        for e in d.get("entries") or []:
            if isinstance(e, dict) and e.get("grapheme") and e.get("phonemes"):
                out.setdefault(str(e["grapheme"]).lower(), list(e["phonemes"]))
    return out


def _cmu(word: str) -> list[str]:
    import cmudict

    d = _cmu_dict()
    pron = d.get(word.lower())
    return [re.sub(r"\d", "", p).lower() for p in pron[0]] if pron else []


@lru_cache(maxsize=1)
def _cmu_dict():
    import cmudict

    return cmudict.dict()


VOWELS = {"aa", "ae", "ah", "ao", "aw", "ax", "ay", "eh", "er", "ey", "ih", "iy", "ow", "oy", "uh", "uw"}


def phonemes_for(word: str, table: dict, cache: str) -> list[str]:
    w = re.sub(r"[^a-z']", "", word.lower())
    ph = _dictionary(cache).get(w) or _cmu(w) or ["ah"]
    out = []
    for p in ph:
        for cand in (p, f"en/{p}", p.split("/")[-1]):
            if cand in table:
                out.append(cand)
                break
    return out or [next(iter(k for k in table if k.split("/")[-1] == "ah"), next(iter(table)))]


def _map(p: str, table: dict) -> list[str]:
    for cand in (p, f"en/{p}", p.split("/")[-1]):
        if cand in table:
            return [cand]
    return []


def _is_vowel(p: str) -> bool:
    return p.split("/")[-1] in VOWELS


def _speaker(cfg: dict, wanted: str | None) -> np.ndarray:
    """One of the voicebank's voice colours (.emb, float32 per hidden unit). 'fresh' is the plainest."""
    vb = voicebank(_CACHE[0])
    names = cfg.get("speakers") or []
    pick = next((n for n in names if wanted and n.endswith(wanted)), None) or next((n for n in names if n.endswith("fresh")), names[0])
    emb = np.fromfile(str(vb / f"{pick}.emb"), dtype=np.float32)
    return emb.reshape(1, -1)


_CACHE: list[str] = [""]


def render(payload: dict, out_path: str, cache: str) -> None:
    _CACHE[0] = cache
    import soundfile as sf

    cfg, acoustic, vocoder, table, _ = _models(cache)
    sr = int(cfg.get("sample_rate", 44100))
    hop = int(cfg.get("hop_size", 512))
    fps = sr / hop
    bpm = float(payload.get("bpm", 90))
    spb = 60.0 / bpm
    notes = sorted(payload["notes"], key=lambda n: n["start"])
    words = list(payload.get("words") or [])
    tokens: list[int] = []
    durs: list[int] = []
    f0: list[float] = []
    t_frames = 0
    lead = int(float(payload.get("lead_s", 0.3)) * fps)
    per_note = payload.get("phonemes")          # [[ "l", "ah" ], ...] one syllable per note, from Frank
    sp = next((k for k in ("SP", "sp", "pau", "AP") if k in table), None)
    if sp is not None and lead > 0:
        tokens.append(table[sp]); durs.append(lead); f0 += [220.0] * lead; t_frames = lead
    prev_hz = None
    for i, n in enumerate(notes):
        start = int(lead + float(n["start"]) * spb * fps)
        end = int(lead + (float(n["start"]) + float(n["duration"])) * spb * fps)
        if start > t_frames and sp is not None:
            gap = start - t_frames
            tokens.append(table[sp]); durs.append(gap); f0 += [prev_hz or 220.0] * gap; t_frames = start
        if per_note and i < len(per_note) and per_note[i]:
            ph = [m for p in per_note[i] for m in _map(p, table)] or phonemes_for("oo", table, cache)
        else:
            ph = phonemes_for(words[i] if i < len(words) else "oo", table, cache)
        cons_before = [p for p in ph[: next((k for k, p in enumerate(ph) if _is_vowel(p)), len(ph))]]
        rest = ph[len(cons_before):] or ["ah"]
        hz = 440.0 * 2 ** ((int(n["note"]) - 69) / 12)
        c_frames = max(1, int(CONSONANT_S * fps))
        for p in cons_before:
            take = min(c_frames, max(1, (end - t_frames) // (len(ph) + 1)))
            tokens.append(table[p]); durs.append(take); f0 += [prev_hz or hz] * take; t_frames += take
        remain = max(len(rest), end - t_frames)
        vowel_frames = remain - (len(rest) - 1) * c_frames if len(rest) > 1 else remain
        for k, p in enumerate(rest):
            take = max(1, vowel_frames if k == 0 else c_frames)
            glide = np.linspace(prev_hz or hz, hz, min(take, int(0.06 * fps)) or 1)
            seg = list(glide) + [hz] * (take - len(glide))
            tokens.append(table[p]); durs.append(take); f0 += seg[:take]; t_frames += take
        prev_hz = hz
    if sp is not None:
        tail = max(lead, int(0.3 * fps))
        tokens.append(table[sp]); durs.append(tail); f0 += [prev_hz or 220.0] * tail
    n_frames = int(sum(durs))
    f0_arr = np.asarray(f0[:n_frames] + [f0[-1]] * max(0, n_frames - len(f0)), dtype=np.float32)
    feeds = {}
    for inp in acoustic.get_inputs():
        name = inp.name
        if name == "tokens":
            feeds[name] = np.asarray([tokens], dtype=np.int64)
        elif name == "durations":
            feeds[name] = np.asarray([durs], dtype=np.int64)
        elif name == "f0":
            feeds[name] = f0_arr[None, :]
        elif name in ("speedup", "depth", "steps"):
            feeds[name] = np.asarray(10 if name == "speedup" else (0.4 if name == "depth" else 20),
                                     dtype=np.int64 if name != "depth" else np.float32)
        elif name in ("gender", "velocity", "energy", "breathiness", "voicing", "tension"):
            feeds[name] = np.full((1, n_frames), 1.0 if name == "velocity" else (-12.0 if name == "breathiness" else 0.0), dtype=np.float32)
        elif name == "spk_embed":
            feeds[name] = np.repeat(_speaker(cfg, payload.get("voice")), n_frames, axis=0)[None, :, :]
        elif name == "languages":
            feeds[name] = np.zeros((1, len(tokens)), dtype=np.int64)
    mel = acoustic.run(None, feeds)[0]
    vfeeds = {}
    for inp in vocoder.get_inputs():
        vfeeds[inp.name] = mel if "mel" in inp.name else f0_arr[None, : mel.shape[1]]
    wav = vocoder.run(None, vfeeds)[0].reshape(-1)
    wav = wav / (np.abs(wav).max() + 1e-9) * 0.8
    sf.write(out_path, wav.astype(np.float32), sr)
