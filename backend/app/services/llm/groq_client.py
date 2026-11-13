"""
Groq LLM client for Frank's conversation layer.
The LLM interprets the user's plain language and emits structured JSON.
It never produces audio — only parameters and messages.
"""

import json
from groq import Groq
from app.config import get_settings

# Groq's hosted model lineup changed; llama-3.3-70b-versatile is no longer
# available on this account. gpt-oss-120b is the strongest general chat model
# currently offered on the free tier and supports JSON mode, which Frank's
# structured conversation layer depends on.
MODEL = "openai/gpt-oss-120b"


def get_groq() -> Groq:
    settings = get_settings()
    return Groq(api_key=settings.groq_api_key)


def chat_structured(
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.7,
) -> dict:
    """
    Send a conversation to Groq and get back a structured JSON response.
    The system prompt must instruct the model to respond with JSON containing
    at least a "message" field and an "actions" array.

    Returns the parsed JSON dict. Falls back gracefully if parsing fails.
    """
    client = get_groq()

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    completion = client.chat.completions.create(
        model=MODEL,
        messages=full_messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    raw = completion.choices[0].message.content or "{}"

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Model returned something non-JSON — wrap it as a plain message
        return {"message": raw, "actions": []}

    # Ensure the required shape
    if "message" not in parsed:
        parsed["message"] = ""
    if "actions" not in parsed or not isinstance(parsed["actions"], list):
        parsed["actions"] = []

    return parsed


def chat_text(system_prompt: str, user_message: str, temperature: float = 0.5) -> str:
    """
    Simple text completion — used for things like generating a plain-language
    description of a hum, where no structured output is needed.
    """
    client = get_groq()
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
    )
    return completion.choices[0].message.content or ""


def chat_json(system_prompt: str, user_message: str, temperature: float = 0.0) -> str:
    """
    One question, one JSON answer, returned as raw text. The caller parses and validates it
    (and decides what to do when it is wrong); nothing is added to the shape.

    Defaults to temperature 0: this is for reading and measuring, where the same input should give
    the same answer. Creative replies use chat_structured.
    """
    client = get_groq()
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
        max_tokens=4000,   # generous: the model also spends tokens thinking before it answers
    )
    return completion.choices[0].message.content or "{}"
