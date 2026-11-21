"""
frank-ears: the models Frank listens with (frankenstein spec 14, section D). A Gradio app on a Hugging Face ZeroGPU
Space, called only by Frank's backend (backend/app/services/remote/spaces.py). Every endpoint takes a file or JSON
and returns JSON or a file; models load on first use. Functions marked @spaces.GPU borrow a GPU for the call;
everything else runs on the Space's CPU, so a day without GPU time still leaves most of Frank's ears working.

Endpoints (api_name):
  /health          "ok"
  /embed_audio     CLAP: 512 numbers for a sound
  /embed_text      CLAP: 512 numbers for each phrase (JSON list in, JSON out)
  /labels          Discogs-EffNet styles (400) and MTG-Jamendo moods: top scores
  /aesthetics      Meta Audiobox Aesthetics: production quality, complexity, enjoyment, usefulness (1..10)
  /structure       All-In-One: speed, beats, downbeats, sections with labels                  (GPU)
  /chords          madmom: chord per stretch of time
  /separate        BS-RoFormer (audio-separator): voice and music apart                       (GPU)
  /pitch           PESTO: pitch every 10 ms with confidence
  /emotions        GoEmotions: feelings in each line of words (JSON list in)
  /describe        one call for a reference song: labels + CLAP words + chords + speed
  /match_master    Matchering: master a song to match a reference's loudness, tone and width
  /denoise         DeepFilterNet: take the background noise out of a voice recording
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from functools import lru_cache

import gradio as gr
import numpy as np

try:
    import spaces  # ZeroGPU
    GPU = spaces.GPU
except Exception:  # noqa: BLE001 - running locally without ZeroGPU
    def GPU(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

SR_CLAP = 48000
FEELING_PHRASES = [
    "calm", "melancholic", "sad", "hopeful", "joyful", "romantic", "dark", "mysterious", "dreamy", "nostalgic",
    "energetic", "aggressive", "uplifting", "tense", "peaceful", "playful", "lonely", "warm", "cold", "epic",
    "intimate", "spacious", "groovy", "laid-back", "haunting", "tender", "triumphant", "gritty", "bright", "hazy",
]


def _load(path: str, sr: int, max_s: float = 360.0) -> np.ndarray:
    import librosa

    y, _ = librosa.load(path, sr=sr, mono=True, duration=max_s)
    return y.astype(np.float32)


def _path(f) -> str:
    return f if isinstance(f, str) else getattr(f, "name", None) or f["path"]


# ── CLAP ─────────────────────────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _clap():
    from transformers import ClapModel, ClapProcessor

    name = "laion/larger_clap_music_and_speech"
    return ClapModel.from_pretrained(name).eval(), ClapProcessor.from_pretrained(name)


def _norm(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


def clap_audio(y48: np.ndarray) -> np.ndarray:
    import torch

    model, proc = _clap()
    win = SR_CLAP * 10
    chunks = [y48[i:i + win] for i in range(0, max(1, len(y48) - win // 2), win)][:12] or [y48]
    with torch.no_grad():
        inp = proc(audios=chunks, sampling_rate=SR_CLAP, return_tensors="pt", padding=True)
        emb = model.get_audio_features(**inp).numpy()
    return _norm(_norm(emb).mean(axis=0))


def clap_text(texts: list[str]) -> np.ndarray:
    import torch

    model, proc = _clap()
    with torch.no_grad():
        inp = proc(text=texts, return_tensors="pt", padding=True)
        return _norm(model.get_text_features(**inp).numpy())


def embed_audio(f) -> str:
    v = clap_audio(_load(_path(f), SR_CLAP, 120))
    return json.dumps({"model": "clap-larger-music-speech", "embedding": [round(float(x), 6) for x in v]})


def embed_text(texts_json: str) -> str:
    texts = [str(t)[:300] for t in json.loads(texts_json)][:64]
    m = clap_text(texts)
    return json.dumps({"model": "clap-larger-music-speech", "embeddings": [[round(float(x), 6) for x in r] for r in m]})


@lru_cache(maxsize=1)
def _feeling_matrix() -> np.ndarray:
    return clap_text([f"music that feels {w}" for w in FEELING_PHRASES])


def clap_words(v: np.ndarray, k: int = 5) -> list[str]:
    sims = _feeling_matrix() @ v
    return [FEELING_PHRASES[i] for i in np.argsort(-sims)[:k]]


# ── Discogs-EffNet styles and MTG-Jamendo moods (ONNX, CC BY-NC-SA 4.0) ───────────────────────────────────

MODELS = "https://essentia.upf.edu/models"


@lru_cache(maxsize=1)
def _effnet():
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download  # noqa: F401  (cache dir only)
    import urllib.request

    d = os.path.join(tempfile.gettempdir(), "effnet")
    os.makedirs(d, exist_ok=True)
    files = {
        "effnet": f"{MODELS}/feature-extractors/discogs-effnet/discogs-effnet-bsdynamic-1.onnx",
        "effnet_json": f"{MODELS}/feature-extractors/discogs-effnet/discogs-effnet-bsdynamic-1.json",
        "mood": f"{MODELS}/classification-heads/mtg_jamendo_moodtheme/mtg_jamendo_moodtheme-discogs-effnet-1.onnx",
        "mood_json": f"{MODELS}/classification-heads/mtg_jamendo_moodtheme/mtg_jamendo_moodtheme-discogs-effnet-1.json",
    }
    local = {}
    for k, u in files.items():
        p = os.path.join(d, os.path.basename(u))
        if not os.path.exists(p):
            urllib.request.urlretrieve(u, p)
        local[k] = p
    eff = ort.InferenceSession(local["effnet"], providers=["CPUExecutionProvider"])
    mood = ort.InferenceSession(local["mood"], providers=["CPUExecutionProvider"])
    styles = json.load(open(local["effnet_json"]))["classes"]
    moods = json.load(open(local["mood_json"]))["classes"]
    return eff, mood, styles, moods


def _mel_patches(path: str) -> np.ndarray:
    """Essentia's TensorflowInputMusiCNN mel bands at 16 kHz, cut into 128-frame patches hopping 62 frames."""
    import essentia.standard as es

    audio = es.MonoLoader(filename=path, sampleRate=16000, resampleQuality=4)()[: 16000 * 360]
    mel = es.TensorflowInputMusiCNN()
    frames = []
    for frame in es.FrameGenerator(audio, frameSize=512, hopSize=256, startFromZero=True):
        frames.append(mel(frame))
    bands = np.array(frames, dtype=np.float32)              # (T, 96)
    if len(bands) < 128:
        bands = np.pad(bands, ((0, 128 - len(bands)), (0, 0)))
    patches = [bands[i:i + 128] for i in range(0, len(bands) - 127, 62)]
    return np.stack(patches)                               # (N, 128, 96)


def labels_for(path: str, k: int = 6) -> dict:
    eff, mood, styles, moods = _effnet()
    x = _mel_patches(path)
    outs = eff.run(None, {eff.get_inputs()[0].name: x})
    probs = next(o for o in outs if o.ndim == 2 and o.shape[1] == len(styles))
    embs = next(o for o in outs if o.ndim == 2 and o.shape[1] == 1280)
    p = probs.mean(axis=0)
    mo = mood.run(None, {mood.get_inputs()[0].name: embs.astype(np.float32)})[0].mean(axis=0)
    top = np.argsort(-p)[:k]
    topm = np.argsort(-mo)[:k]
    return {"styles": [{"name": styles[i].split("---")[-1], "family": styles[i].split("---")[0], "score": round(float(p[i]), 3)} for i in top],
            "moods": [{"name": moods[i], "score": round(float(mo[i]), 3)} for i in topm]}


def labels(f) -> str:
    return json.dumps(labels_for(_path(f)))


# ── Audiobox Aesthetics (CC BY 4.0) ──────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _aes():
    from audiobox_aesthetics.infer import initialize_predictor

    return initialize_predictor()


@GPU(duration=20)
def aesthetics(f) -> str:
    r = _aes().forward([{"path": _path(f)}])[0]
    names = {"PQ": "made_well", "PC": "how_much_going_on", "CE": "enjoyment", "CU": "usefulness"}
    return json.dumps({names.get(k, k): round(float(v), 2) for k, v in r.items()})


# ── All-In-One structure (MIT) ───────────────────────────────────────────────────────────────────────────

@GPU(duration=45)
def _allin1(path: str) -> dict:
    import allin1_infer as allin1

    r = allin1.analyze(path)
    return {"bpm": r.bpm, "beats": [round(float(b), 3) for b in r.beats], "downbeats": [round(float(b), 3) for b in r.downbeats],
            "sections": [{"start": round(float(s.start), 2), "end": round(float(s.end), 2), "label": s.label} for s in r.segments]}


def structure(f) -> str:
    return json.dumps(_allin1(_path(f)))


# ── chords (madmom, CC BY-NC-SA models) ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _chord_procs():
    from madmom.features.chords import CNNChordFeatureProcessor, CRFChordRecognitionProcessor

    return CNNChordFeatureProcessor(), CRFChordRecognitionProcessor()


def chords_for(path: str) -> list[dict]:
    feat, crf = _chord_procs()
    out = crf(feat(path))
    return [{"start": round(float(s), 2), "end": round(float(e), 2), "chord": str(c)} for s, e, c in out]


def chords(f) -> str:
    return json.dumps({"chords": chords_for(_path(f))})


# ── separation (BS-RoFormer via audio-separator, MIT) ────────────────────────────────────────────────────

ROFORMER = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"


@GPU(duration=60)
def _separate(path: str, out_dir: str) -> list[str]:
    from audio_separator.separator import Separator

    sep = Separator(output_dir=out_dir, output_format="MP3", model_file_dir=os.path.join(tempfile.gettempdir(), "sep-models"))
    sep.load_model(model_filename=ROFORMER)
    return [os.path.join(out_dir, p) if not os.path.isabs(p) else p for p in sep.separate(path)]


def separate(f):
    d = tempfile.mkdtemp(prefix="sep-")
    files = _separate(_path(f), d)
    vocal = next((p for p in files if "ocal" in os.path.basename(p)), files[0])
    music = next((p for p in files if p != vocal), files[-1])
    return vocal, music


# ── pitch (PESTO, LGPL) ─────────────────────────────────────────────────────────────────────────────────

def pitch(f) -> str:
    import pesto
    import torch

    y = _load(_path(f), 16000, 120)
    t, p, c, _ = pesto.predict(torch.from_numpy(y), 16000, step_size=10.0)
    return json.dumps({"time": [round(float(x) / 1000.0, 3) for x in t], "hz": [round(float(x), 2) for x in p],
                       "confidence": [round(float(x), 3) for x in c]})


# ── emotions in words (GoEmotions, MIT) ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _emo():
    from transformers import pipeline

    return pipeline("text-classification", model="SamLowe/roberta-base-go_emotions", top_k=None)


@GPU(duration=15)
def emotions(lines_json: str) -> str:
    lines = [str(l)[:400] for l in json.loads(lines_json)][:200]
    res = _emo()(lines) if lines else []
    out = []
    for r in res:
        top = sorted(r, key=lambda x: -x["score"])[:3]
        out.append([{"name": x["label"], "score": round(float(x["score"]), 3)} for x in top])
    return json.dumps({"lines": out})


# ── one call for a reference song ───────────────────────────────────────────────────────────────────────

def describe(f) -> str:
    path = _path(f)
    out: dict = {}
    try:
        out.update(labels_for(path))
    except Exception as e:  # noqa: BLE001
        out["labels_error"] = str(e)[:200]
    try:
        v = clap_audio(_load(path, SR_CLAP, 120))
        out["embedding"] = [round(float(x), 6) for x in v]
        out["feeling_words"] = clap_words(v)
    except Exception as e:  # noqa: BLE001
        out["clap_error"] = str(e)[:200]
    try:
        out["chords"] = chords_for(path)[:200]
    except Exception as e:  # noqa: BLE001
        out["chords_error"] = str(e)[:200]
    return json.dumps(out)


# ── Matchering (GPL-3.0) ────────────────────────────────────────────────────────────────────────────────

def match_master(target, reference):
    import matchering as mg

    out = tempfile.mktemp(suffix=".wav", prefix="matched-")
    mg.process(target=_path(target), reference=_path(reference), results=[mg.pcm16(out)])
    return out


# ── DeepFilterNet (MIT / Apache-2.0) ────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _df():
    # deepfilternet imports a torchaudio module that newer torchaudio removed; it only needs the type name.
    if "torchaudio.backend.common" not in sys.modules:
        mod = types.ModuleType("torchaudio.backend.common")
        mod.AudioMetaData = object
        sys.modules["torchaudio.backend"] = types.ModuleType("torchaudio.backend")
        sys.modules["torchaudio.backend.common"] = mod
    from df.enhance import init_df

    return init_df()


@GPU(duration=30)
def denoise(f):
    import soundfile as sf
    import torch
    from df.enhance import enhance

    model, state, _ = _df()
    y = _load(_path(f), state.sr(), 600)
    out = enhance(model, state, torch.from_numpy(y)[None, :])
    path = tempfile.mktemp(suffix=".wav", prefix="quiet-")
    sf.write(path, out.squeeze(0).numpy(), state.sr())
    return path


def health() -> str:
    return "ok"


ENDPOINTS = [
    (health, [], ["text"]),
    (embed_audio, ["file"], ["text"]),
    (embed_text, ["text"], ["text"]),
    (labels, ["file"], ["text"]),
    (aesthetics, ["file"], ["text"]),
    (structure, ["file"], ["text"]),
    (chords, ["file"], ["text"]),
    (separate, ["file"], ["file", "file"]),
    (pitch, ["file"], ["text"]),
    (emotions, ["text"], ["text"]),
    (describe, ["file"], ["text"]),
    (match_master, ["file", "file"], ["file"]),
    (denoise, ["file"], ["file"]),
]



def _reporting(fn):
    """Errors go back to Frank's backend with the real reason and where it happened (the run log is not always
    readable), as a Gradio error the client receives."""
    import functools
    import traceback

    @functools.wraps(fn)
    def run(*args):
        try:
            return fn(*args)
        except gr.Error:
            raise
        except Exception as e:  # noqa: BLE001
            tb = traceback.extract_tb(e.__traceback__)
            where = "; ".join(f"{p.filename.rsplit('/', 1)[-1]}:{p.lineno}" for p in tb[-3:])
            raise gr.Error(f"{type(e).__name__}: {str(e)[:600]} [{where}]")
    return run


def _component(kind: str):
    return gr.File(visible=False) if kind == "file" else gr.Textbox(visible=False)


with gr.Blocks(title="frank-ears") as demo:
    gr.Markdown("**frank-ears**: the models Frank listens with. An API for Frank's backend, "
                "[github.com/Udeibom/frank](https://github.com/Udeibom/frank). Not a user interface.")
    for fn, ins, outs in ENDPOINTS:
        button = gr.Button(fn.__name__, visible=False)
        button.click(_reporting(fn), [_component(k) for k in ins], [_component(k) for k in outs], api_name=fn.__name__)

demo.queue(default_concurrency_limit=2).launch(show_error=True)
