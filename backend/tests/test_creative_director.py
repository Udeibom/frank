"""Creative Director (spec 10): names become feelings, nothing aims at an artist, drift is said once."""
from __future__ import annotations

import asyncio
import pathlib
import re

from hypothesis import given, settings, strategies as st

from app.models.song import SongRecord
from app.services.song.brief import build_brief
from app.services.team import identity

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def test_a_named_artist_reaches_no_prompt_only_the_feeling_does():
    record = SongRecord(project_id="p", facets={
        "intent": {"text": "a song for my grandmother"},
        "references": {"items": [{"name": "Billie Eilish", "use": "feeling_only", "loved": ["hushed", "close"]}]},
    })
    for role in (None, "beat_maker", "producer", "vocal_producer", "mix_engineer", "songwriter"):
        brief = build_brief(record, role)
        assert "Billie" not in brief and "Eilish" not in brief
        assert "hushed" in brief and "close" in brief


def test_the_reply_fields_are_taken_out_and_kept_as_a_feeling(monkeypatch):
    written: list[tuple[str, dict]] = []

    async def active(project_id, facet):
        return None

    async def write(project_id, facet, content, **kw):
        written.append((facet, content))

    from app.services.song import record as song_record
    from app.services.song import store

    monkeypatch.setattr(song_record, "active_facet", active)
    monkeypatch.setattr(store, "write_facet", write)
    result = {"message": "What do you love about it?", "actions": [], "named_reference": "Billie Eilish", "loved_qualities": ["Hushed", "close"]}
    asyncio.run(identity.handle_reply("p", result))
    assert "named_reference" not in result and "loved_qualities" not in result
    facets = dict(written)
    assert facets["feeling"]["loved_qualities"] == ["hushed", "close"]
    assert facets["references"]["items"][0]["use"] == "feeling_only"


def test_no_part_of_frank_can_search_the_web_or_aim_at_an_artist():
    code = {p: p.read_text() for p in APP.rglob("*.py")}
    llm = (APP / "services/llm/groq_client.py").read_text()
    assert "tools=" not in llm and "web_search" not in llm, "no model is given a tool"
    for p, text in code.items():
        if "/generation/" in str(p):
            assert "references" not in text, f"{p} must never read the named references"
    assert "never the name" in identity.TEAM_RULE and "ONE" in identity.TEAM_RULE


@settings(max_examples=200, deadline=None)
@given(st.sampled_from(["light", "moderate", "full"]), st.booleans(), st.booleans())
def test_lock_it_in_is_questioned_only_when_they_want_it_raw(mode, raw, hates):
    ident = {"keep": ["your voice raw, not tuned hard"] if raw else ["the line about the porch light"], "voice": ""}
    notes = identity.drift_notes(ident, tune_mode=mode, hates_tuning=hates)
    if mode == "full" and (raw or hates):
        assert len(notes) == 1 and "Your call" in notes[0]
    else:
        assert notes == []


def test_taking_their_own_tune_out_is_named_and_other_changes_are_not():
    d = {"title": "Leave the tune out", "kind": "beat", "actions": [{"op": "remove_part", "part": "melody", "section": [2]}]}
    assert identity.drift_notes({}, direction=d, their_tune=True)
    assert not identity.drift_notes({}, direction=d, their_tune=False)
    other = {"title": "Bigger", "kind": "beat", "actions": [{"op": "bigger", "section": [2]}]}
    assert not identity.drift_notes({}, direction=other, their_tune=True)


def test_a_suggestion_that_drops_their_image_says_so():
    ident = {"own_images": ["the porch light"], "own_words": []}
    old = "I left the porch light on\nfor you to find your way"
    assert identity.drift_notes(ident, old_text=old, new_text="I kept a candle burning\nfor you to find your way")
    assert not identity.drift_notes(ident, old_text=old, new_text="the porch light is still on\nI wait")
    lyrics = "Verse 1\nwalking slow\n\n[Chorus]\nI left the porch light on\nfor you\n\nBridge:\nlater"
    assert identity.section_text(lyrics, "Chorus") == "I left the porch light on\nfor you"
    assert identity.section_text(lyrics, "Outro") is None


def test_the_identity_brief_is_plain_and_bounded():
    raw = {"own_words": ["the rain", "my grandmother's hands"] + ["x"] * 10, "own_images": [3, None, "porch light"],
           "voice": "soft and close", "keep": ["her name in the chorus"], "avoid": "not a list"}
    out = identity.clean_identity(raw)
    assert len(out["own_words"]) <= 6 and out["own_images"] == ["3", "porch light"] and out["avoid"] == []
    assert not re.search(r"\bBPM\b|reverb", " ".join(sum((v if isinstance(v, list) else [v] for v in out.values()), [])))


def test_names_are_spotted_and_answered_with_one_plain_question(monkeypatch):
    assert identity.detect_reference("I want it to sound like Billie Eilish") == "Billie Eilish"
    assert identity.detect_reference("something like The Weeknd but slower") == "The Weeknd"
    assert identity.detect_reference("make it feel like rain on a window") is None
    assert identity.detect_reference("I like it") is None

    async def nothing(*a, **k):
        return None

    from app.services.song import record as song_record
    from app.services.song import store

    monkeypatch.setattr(song_record, "active_facet", nothing)
    monkeypatch.setattr(store, "write_facet", nothing)
    result = {"message": "Billie Eilish's world feels intimate and eerie. What pulls you in?",
              "fingerprint_update": {"genre_proximity": ["pop"]}, "actions": [{"type": "generate_texture"}]}
    asyncio.run(identity.handle_reply("p", result, "I want it to sound like Billie Eilish", "feel"))
    assert result["message"] == identity.ASK and result["message"].count("?") == 1
    assert "fingerprint_update" not in result and result["actions"] == []
    assert not any(w in result["message"].lower() for w in ("you shouldn't", "instead of copying", "original"))
    assert set(identity.feelings_in("the whisper-like closeness, it's so close and dark")) == {"close", "whisper", "dark"}
