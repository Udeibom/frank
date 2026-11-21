"""
frank-hands: the models Frank makes things with (frankenstein spec 14, section E). Gradio on a ZeroGPU Space, called
only by Frank's backend. Generators return notes or parameters where they can, so Frank's own engine still plays
and owns the result; where they return audio it becomes one named, removable layer.

Endpoints (api_name):
  /health      "ok"
  /accompany   Anticipatory Music Transformer: notes around a melody (JSON in, JSON notes out)      (GPU)
  /timbre      DDSP: a hum or a voice played as violin, flute, trumpet, saxophone...  (file out)  (CPU, own env)
  /speak       Kokoro: Frank's note read aloud (mp3 out)
  /ambience    Stable Audio 3 Small / Open: a short atmosphere from words (file out)              (GPU)
  /sing        DiffSinger (Tiger voicebank): a guide voice singing the words on the tune            (CPU)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

import gradio as gr
import numpy as np

try:
    import spaces
    GPU = spaces.GPU
except Exception:  # noqa: BLE001
    def GPU(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

HERE = Path(__file__).resolve().parent
CACHE = Path(tempfile.gettempdir()) / "frank-hands"
CACHE.mkdir(exist_ok=True)


def _path(f) -> str:
    return f if isinstance(f, str) else getattr(f, "name", None) or f["path"]


# ── Anticipatory Music Transformer (Apache-2.0) ─────────────────────────────────────────────────────────

AMT_MODEL = "stanford-crfm/music-medium-800k"


@lru_cache(maxsize=1)
def _amt():
    from transformers import AutoModelForCausalLM

    return AutoModelForCausalLM.from_pretrained(AMT_MODEL)


def _melody_midi(notes: list[dict], bpm: float, program: int) -> str:
    import mido

    tpb = 480
    mid = mido.MidiFile(ticks_per_beat=tpb)
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    tr.append(mido.Message("program_change", program=program, channel=0, time=0))
    ev = []
    for n in notes:
        a = int(float(n["start"]) * tpb)
        b = max(a + 1, int((float(n["start"]) + float(n["duration"])) * tpb))
        ev += [(a, 1, mido.Message("note_on", note=int(n["note"]), velocity=int(n.get("velocity", 90)), channel=0)),
               (b, 0, mido.Message("note_off", note=int(n["note"]), velocity=0, channel=0))]
    now = 0
    for t, _, m in sorted(ev, key=lambda x: (x[0], x[1])):
        m.time = t - now
        now = t
        tr.append(m)
    mid.tracks.append(tr)
    p = tempfile.mktemp(suffix=".mid")
    mid.save(p)
    return p


@GPU(duration=120)
def _amt_generate(melody_path: str, seconds: float, top_p: float) -> list:
    import torch
    from anticipation import ops
    from anticipation.convert import midi_to_events
    from anticipation.sample import generate
    from anticipation.tokenize import extract_instruments

    model = _amt().to("cuda" if torch.cuda.is_available() else "cpu")
    events = midi_to_events(melody_path)
    events, controls = extract_instruments(events, [0])
    out = generate(model, start_time=0, end_time=seconds, inputs=[], controls=controls, top_p=top_p)
    return ops.clip(out, 0, seconds)


def accompany(payload: str) -> str:
    """payload: {"notes": [{note, start (beats), duration (beats), velocity}], "bpm", "beats", "top_p"?}.
    Returns {"parts": [{"program", "notes": [...]}]} in beats, the melody itself left out."""
    from anticipation.convert import events_to_midi

    p = json.loads(payload)
    bpm = float(p.get("bpm", 90))
    seconds = float(p.get("beats", 32)) * 60.0 / bpm
    mel = _melody_midi(p["notes"], bpm, 0)
    events = _amt_generate(mel, seconds, float(p.get("top_p", 0.95)))
    mid = events_to_midi(events)
    spb = mid.ticks_per_beat
    tempo = 500000
    parts: dict[int, list] = {}
    for track in mid.tracks:
        t = 0
        prog: dict[int, int] = {}
        on: dict[tuple, tuple] = {}
        for m in track:
            t += m.time
            if m.type == "set_tempo":
                tempo = m.tempo
            elif m.type == "program_change":
                prog[m.channel] = m.program
            elif m.type == "note_on" and m.velocity > 0:
                on[(m.channel, m.note)] = (t, m.velocity)
            elif m.type in ("note_off", "note_on"):
                k = (m.channel, m.note)
                if k in on:
                    a, v = on.pop(k)
                    sec_per_tick = tempo / 1e6 / spb
                    start_b = a * sec_per_tick * bpm / 60.0
                    dur_b = max(0.05, (t - a) * sec_per_tick * bpm / 60.0)
                    key = 128 if m.channel == 9 else prog.get(m.channel, 0)
                    parts.setdefault(key, []).append({"note": m.note, "start": round(start_b, 4), "duration": round(dur_b, 4), "velocity": v})
    out = [{"program": k, "drums": k == 128, "notes": v} for k, v in parts.items()]
    out.sort(key=lambda x: -len(x["notes"]))
    return json.dumps({"parts": out})


# ── DDSP timbre transfer (Apache-2.0), in its own environment because it needs TensorFlow ──────────────

DDSP_ENV = CACHE / "ddsp-env"
DDSP_INSTRUMENTS = ["violin", "flute", "flute2", "trumpet", "tenor_saxophone"]


def _ddsp_env() -> Path:
    py = DDSP_ENV / "bin" / "python"
    if not py.exists():
        subprocess.run([sys.executable, "-m", "venv", str(DDSP_ENV)], check=True)
        subprocess.run([str(py), "-m", "pip", "install", "-q", "ddsp==3.7.0", "tensorflow==2.15.1",
                        "tensorflow-probability==0.23.0", "numpy<1.27", "crepe==0.0.16"], check=True, timeout=1500)
    return py


def timbre(f, instrument: str) -> str:
    instrument = instrument if instrument in DDSP_INSTRUMENTS else "violin"
    out = tempfile.mktemp(suffix=".wav", prefix="timbre-")
    subprocess.run([str(_ddsp_env()), str(HERE / "ddsp_worker.py"), _path(f), instrument, out, str(CACHE)],
                   check=True, timeout=900, capture_output=True)
    return out


# ── Kokoro (Apache-2.0) ─────────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _kokoro():
    from kokoro import KPipeline

    return KPipeline(lang_code="a")


def speak(text: str, voice: str = "af_heart") -> str:
    import soundfile as sf

    chunks = [a for _, _, a in _kokoro()(text[:1200], voice=voice or "af_heart")]
    audio = np.concatenate([np.asarray(c) for c in chunks]) if chunks else np.zeros(2400, dtype=np.float32)
    wav = tempfile.mktemp(suffix=".wav")
    sf.write(wav, audio, 24000)
    mp3 = wav[:-4] + ".mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-b:a", "64k", mp3], check=True)
    return mp3


# ── Stable Audio (Stability AI Community Licence) ───────────────────────────────────────────────────────

STABLE_MODELS = ["stabilityai/stable-audio-3-small-music", "stabilityai/stable-audio-open-small", "stabilityai/stable-audio-open-1.0"]


@lru_cache(maxsize=1)
def _stable():
    try:
        import stable_audio_tools  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--ignore-requires-python",
                        "stable-audio-tools==0.0.20", "v-diffusion-pytorch==0.0.2"], check=True, timeout=900)
    from stable_audio_tools import get_pretrained_model

    last = None
    for name in STABLE_MODELS:
        try:
            model, cfg = get_pretrained_model(name)
            return model, cfg, name
        except Exception as e:  # noqa: BLE001 - gated or missing: try the next
            last = e
    raise RuntimeError(f"no Stable Audio model available: {last}")


@GPU(duration=90)
def _ambience(prompt: str, seconds: float) -> str:
    import torch
    import torchaudio
    from stable_audio_tools.inference.generation import generate_diffusion_cond

    model, cfg, name = _stable()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(dev)
    sr = cfg["sample_rate"]
    size = cfg["sample_size"]
    steps = 8 if "small" in name else 80
    sampler = "pingpong" if "small" in name else "dpmpp-3m-sde"
    audio = generate_diffusion_cond(model, steps=steps, cfg_scale=1.0 if "small" in name else 7.0,
                                    conditioning=[{"prompt": prompt, "seconds_total": seconds}],
                                    sample_size=size, sampler_type=sampler, device=dev)
    audio = audio[0, :, : int(seconds * sr)].to(torch.float32)
    audio = (audio / (audio.abs().max() + 1e-9)).clamp(-1, 1).cpu()
    out = tempfile.mktemp(suffix=".wav", prefix="ambience-")
    torchaudio.save(out, audio, sr)
    return out


def ambience(prompt: str, seconds: float) -> str:
    wav = _ambience(prompt[:400], float(max(5.0, min(30.0, seconds))))
    mp3 = wav[:-4] + ".mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-b:a", "160k", mp3], check=True)
    return mp3


# ── DiffSinger guide voice (Tiger voicebank, CC BY-NC-ND 4.0 + Commons Clause) ──────────────────────────

def sing(payload: str) -> str:
    """payload: {"notes": [{note, start, duration}], "words": ["one", "syllable", "per", "note"], "bpm"}."""
    from diffsinger_worker import render

    out = tempfile.mktemp(suffix=".wav", prefix="sing-")
    render(json.loads(payload), out, str(CACHE))
    mp3 = out[:-4] + ".mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out, "-b:a", "128k", mp3], check=True)
    return mp3


def sing_layout() -> str:
    from diffsinger_worker import layout

    return json.dumps(layout(str(CACHE)))


def health() -> str:
    return "ok"


ENDPOINTS = [
    (health, [], ["text"]),
    (accompany, ["text"], ["text"]),
    (timbre, ["file", "text"], ["file"]),
    (speak, ["text", "text"], ["file"]),
    (ambience, ["text", "number"], ["file"]),
    (sing, ["text"], ["file"]),
    (sing_layout, [], ["text"]),
]


def _component(kind: str):
    if kind == "file":
        return gr.File(visible=False)
    if kind == "number":
        return gr.Number(visible=False)
    return gr.Textbox(visible=False)


sys.path.insert(0, str(HERE))
with gr.Blocks(title="frank-hands") as demo:
    gr.Markdown("**frank-hands**: the models Frank makes things with. An API for Frank's backend, "
                "[github.com/Udeibom/frank](https://github.com/Udeibom/frank). Not a user interface.")
    for fn, ins, outs in ENDPOINTS:
        button = gr.Button(fn.__name__, visible=False)
        button.click(fn, [_component(k) for k in ins], [_component(k) for k in outs], api_name=fn.__name__)

demo.queue(default_concurrency_limit=1).launch(show_error=True)
