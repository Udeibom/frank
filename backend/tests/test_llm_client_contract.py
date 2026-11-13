"""
The model calls must match the library that is actually installed.

A fake model answer in a unit test cannot notice that we passed the client an argument it does not
accept (this happened: `max_completion_tokens` against groq 0.13). These tests bind our real call to
the real library's signature without touching the network.
"""
import inspect

import pytest
from groq.resources.chat.completions import Completions

from app.services.llm import groq_client

ACCEPTED = set(inspect.signature(Completions.create).parameters) - {"self"}


class _Reply:
    class _Choice:
        class _Message:
            content = '{"ok": true}'

        message = _Message()

    choices = [_Choice()]


class _CheckedCompletions:
    """Accepts exactly what the installed library accepts, and nothing else."""

    def __init__(self):
        self.seen: list[dict] = []

    def create(self, **kwargs):
        unknown = set(kwargs) - ACCEPTED
        if unknown:
            raise TypeError(f"Completions.create() got unexpected keyword argument(s) {sorted(unknown)}")
        self.seen.append(kwargs)
        return _Reply()


class _FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": _CheckedCompletions()})()


@pytest.fixture
def client(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(groq_client, "get_groq", lambda: fake)
    return fake


def test_chat_json_only_passes_arguments_the_installed_library_accepts(client):
    assert groq_client.chat_json("system", "user") == '{"ok": true}'
    sent = client.chat.completions.seen[0]
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["temperature"] == 0.0
    assert 0 < sent["max_tokens"] <= 8000


def test_chat_structured_only_passes_arguments_the_installed_library_accepts(client):
    groq_client.chat_structured("system", [{"role": "user", "content": "hi"}])
    assert client.chat.completions.seen


def test_chat_text_only_passes_arguments_the_installed_library_accepts(client):
    groq_client.chat_text("system", "hi")
    assert client.chat.completions.seen


def test_the_checker_itself_refuses_an_argument_the_library_does_not_know():
    with pytest.raises(TypeError):
        _CheckedCompletions().create(model="m", messages=[], max_completion_tokens=5)
