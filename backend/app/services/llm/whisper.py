"""
Speech-to-text via Whisper, hosted on Groq.
Used in the Idea Room to transcribe voice memos of song ideas.
Runs on the backend — no local model inference.

Note: originally planned for Hugging Face's Inference API, but HF retired the
old api-inference.huggingface.co domain. Groq hosts whisper-large-v3-turbo
directly, it's the same provider as our chat model, already authenticated,
and faster — so Frank transcribes through Groq.
"""

from app.services.llm.groq_client import get_groq

WHISPER_MODEL = "whisper-large-v3-turbo"


async def transcribe(wav_bytes: bytes) -> str:
    """
    Send WAV audio to Groq Whisper and return the transcription text.
    """
    client = get_groq()
    result = client.audio.transcriptions.create(
        file=("memo.wav", wav_bytes),
        model=WHISPER_MODEL,
    )
    return (result.text or "").strip()
