"""
When each sung word happens (frankenstein spec 14, requirement 4.4).

Groq's Whisper returns word timings for a take. Matching them to the person's own lyric lines gives each line a
start and end in the take, which is what "redo the second line", line-by-line comping and following along in the
Words room need. Whisper mishears singing, so matching is by similarity, not exact words, and a line it cannot
place is left without times rather than guessed.
"""
from __future__ import annotations

import difflib
import re
import subprocess
from typing import Optional

WORD = re.compile(r"[a-z0-9']+")


def norm(text: str) -> list[str]:
    return WORD.findall(text.lower().replace("’", "'"))


def lyric_lines(lyrics: Optional[str]) -> list[str]:
    """Sung lines only: no blank lines and no section headings like [Chorus] or Verse 2:."""
    out = []
    for line in (lyrics or "").splitlines():
        s = line.strip()
        if not s or re.match(r"^[\[(]?\s*(intro|verse|pre-?chorus|chorus|hook|refrain|bridge|outro)\b[^\])]*[\])]?\s*:?\s*$", s, re.I):
            continue
        out.append(s)
    return out


def line_spans(words: list[dict], lines: list[str], min_share: float = 0.4) -> list[dict]:
    """
    For each lyric line, the time span of the sung words that match it. `words` is [{word, start, end}] in order.
    A line is placed only when at least `min_share` of its words were matched; spans never overlap or go backwards.
    """
    # Match letter by letter, so "street lights" and "streetlights" (or "gonna" and "gon na") still line up.
    sung: list[tuple[str, int]] = [(c, i) for i, w in enumerate(words) for c in "".join(norm(w.get("word", "")))]
    lyric: list[tuple[str, int]] = [(c, li) for li, line in enumerate(lines) for c in "".join(norm(line))]
    matcher = difflib.SequenceMatcher(a=[c for c, _ in lyric], b=[c for c, _ in sung], autojunk=False)
    hits: dict[int, list[int]] = {}
    matched_letters: dict[int, int] = {}
    for block in matcher.get_matching_blocks():
        if block.size < 2:                         # a single shared letter is chance, not a match
            continue
        for k in range(block.size):
            li = lyric[block.a + k][1]
            hits.setdefault(li, []).append(sung[block.b + k][1])
            matched_letters[li] = matched_letters.get(li, 0) + 1
    out = []
    last_end = -1.0
    for li, line in enumerate(lines):
        n = max(1, len("".join(norm(line))))
        idx = sorted(set(hits.get(li, [])))
        entry: dict = {"line": li, "text": line, "start": None, "end": None}
        if idx and matched_letters.get(li, 0) / n >= min_share:
            start = float(words[idx[0]]["start"])
            end = float(words[idx[-1]]["end"])
            if start >= last_end and end > start:
                entry["start"], entry["end"] = round(start, 2), round(end, 2)
                last_end = end
        out.append(entry)
    return out


def to_mp3(wav: bytes) -> bytes:
    """Whisper takes up to 25 MB; a take as a small mono mp3 is always far under that."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000", "-b:a", "48k",
                        "-f", "mp3", "pipe:1"], input=wav, capture_output=True, timeout=120, check=True)
    return r.stdout


def transcribe_words(audio: bytes, name: str = "take.mp3", prompt: Optional[str] = None) -> list[dict]:
    """Word timings from Groq Whisper (sync; call from a worker thread). The lyrics, when known, are the prompt."""
    from app.services.llm.groq_client import get_groq
    from app.services.llm.whisper import WHISPER_MODEL

    kwargs = {"file": (name, audio), "model": WHISPER_MODEL, "response_format": "verbose_json",
              "timestamp_granularities": ["word"]}
    if prompt:
        kwargs["prompt"] = prompt[:800]
    result = get_groq().audio.transcriptions.create(**kwargs)
    raw = getattr(result, "words", None)
    if raw is None and hasattr(result, "model_extra"):
        raw = (result.model_extra or {}).get("words")
    if raw is None and isinstance(result, dict):
        raw = result.get("words")
    out = []
    for w in raw or []:
        get = (lambda k: w.get(k)) if isinstance(w, dict) else (lambda k: getattr(w, k, None))
        if get("word") is not None and get("start") is not None and get("end") is not None:
            out.append({"word": str(get("word")).strip(), "start": round(float(get("start")), 2), "end": round(float(get("end")), 2)})
    return out
