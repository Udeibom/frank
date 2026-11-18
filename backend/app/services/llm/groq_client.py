"""
LLM client for Frank's conversation layer.
The LLM interprets the user's plain language and emits structured JSON. It never produces audio.

Providers (team-conversation spec 07, requirement 8): Groq is primary. When Groq is rate-limited, down or slow,
the same request goes to Google Gemini's free tier through its OpenAI-compatible endpoint (GEMINI_API_KEY). The
person only notices a slightly slower reply. Every reply's "message" passes the plain-language guard (requirement 6).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx
from groq import Groq

from app.config import get_settings
from app.services.team.plain import guard

log = logging.getLogger(__name__)

# Groq's hosted model lineup changed; llama-3.3-70b-versatile is no longer available on this account.
# gpt-oss-120b is the strongest general chat model on the free tier and supports JSON mode.
MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "gemini-flash-latest"   # tracks the current free model (2.5 was retired for new keys, Nov 2026)
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def get_groq() -> Groq:
    settings = get_settings()
    return Groq(api_key=settings.groq_api_key, timeout=60.0, max_retries=1)


def _gemini(messages: list[dict], temperature: float, json_mode: bool, max_tokens: Optional[int]) -> str:
    key = get_settings().gemini_api_key
    if not key:
        raise RuntimeError("no fallback provider configured")
    body: dict[str, Any] = {"model": FALLBACK_MODEL, "messages": messages, "temperature": temperature}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if max_tokens:
        body["max_tokens"] = max_tokens
    r = httpx.post(GEMINI_URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=90.0)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or ""


def _complete(messages: list[dict], temperature: float, json_mode: bool, max_tokens: Optional[int] = None) -> str:
    """One completion: Groq first, Gemini if Groq fails for any reason. Raises only when both fail."""
    kwargs: dict[str, Any] = {"model": MODEL, "messages": messages, "temperature": temperature}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    try:
        completion = get_groq().chat.completions.create(**kwargs)
        return completion.choices[0].message.content or ""
    except Exception as primary:  # noqa: BLE001  rate limit, outage, timeout: try the other provider
        log.warning("groq failed (%s); trying the fallback provider", type(primary).__name__)
        try:
            return _gemini(messages, temperature, json_mode, max_tokens)
        except Exception:  # noqa: BLE001
            raise primary from None


def chat_structured(system_prompt: str, messages: list[dict], temperature: float = 0.7) -> dict:
    """
    A conversation turn that must come back as JSON with a "message" and an "actions" array.
    The message is passed through the plain-language guard before anyone sees it.
    """
    raw = _complete([{"role": "system", "content": system_prompt}] + messages, temperature, json_mode=True) or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"message": guard(raw), "actions": []}
    if not isinstance(parsed, dict):
        parsed = {}
    parsed["message"] = guard(str(parsed.get("message") or ""))
    if not isinstance(parsed.get("actions"), list):
        parsed["actions"] = []
    return parsed


def chat_text(system_prompt: str, user_message: str, temperature: float = 0.5) -> str:
    """Plain text completion (no structure), guarded for plain language."""
    out = _complete([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}], temperature, json_mode=False)
    return guard(out)


def chat_json(system_prompt: str, user_message: str, temperature: float = 0.0) -> str:
    """
    One question, one JSON answer, returned as raw text. The caller parses and validates it.
    Temperature 0: reading and measuring, where the same input should give the same answer.
    """
    return _complete(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        temperature, json_mode=True, max_tokens=4000,   # generous: the model also spends tokens thinking
    ) or "{}"
