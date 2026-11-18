"""Plain-language guard and provider fallback (team-conversation spec 07, requirements 6 and 8)."""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from app.services.llm import groq_client as g
from app.services.team.plain import JARGON, find_jargon, guard


@pytest.mark.parametrize("text", [
    "I pulled the tempo down to 84 BPM.", "Added some reverb on the vocal.", "A little compression on the drums.",
    "Cut 200 Hz by 3 dB with the EQ.", "I muted the bass stem.", "I quantized the drums to the grid.",
    "The DAW export at -14 LUFS.", "Your MIDI notes are in the key of A minor.",
])
def test_jargon_never_reaches_the_person(text):
    out = guard(text)
    assert not JARGON.search(out), out
    assert out and out[0].isupper() or out[0].isdigit() or out


@given(st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Zs", "Po")), max_size=200))
@settings(max_examples=200, deadline=None)
def test_the_guard_always_removes_every_listed_term(text):
    assert not JARGON.search(guard(text))


@pytest.mark.parametrize("text", [
    "The keyboard part is gentle.", "That chorus feels modest.", "Your voice sits right on top now.",
    "I made the drums a little busier in the second verse. How does that feel?",
])
def test_plain_sentences_are_left_exactly_as_they_were(text):
    assert guard(text) == text and find_jargon(text) == []


class _Boom:
    class chat:
        class completions:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("429 rate limited")


def test_when_groq_fails_the_fallback_answers(monkeypatch):
    monkeypatch.setattr(g, "get_groq", lambda: _Boom())
    monkeypatch.setattr(g, "_gemini", lambda msgs, t, j, m: '{"message": "Set to 90 BPM.", "actions": []}')
    out = g.chat_structured("system", [{"role": "user", "content": "hi"}])
    assert out["actions"] == [] and "bpm" not in out["message"].lower()


def test_when_both_providers_fail_the_original_error_is_raised(monkeypatch):
    monkeypatch.setattr(g, "get_groq", lambda: _Boom())

    def down(*a):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(g, "_gemini", down)
    with pytest.raises(RuntimeError, match="429"):
        g.chat_structured("system", [{"role": "user", "content": "hi"}])


def test_a_non_json_reply_is_still_a_guarded_message(monkeypatch):
    monkeypatch.setattr(g, "_complete", lambda *a, **k: "Sure, I added reverb.")
    out = g.chat_structured("s", [])
    assert out == {"message": "Sure, I added space.", "actions": []}
