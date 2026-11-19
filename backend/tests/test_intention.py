"""Protect the intention (team-conversation spec 07, requirement 3.1)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from hypothesis import given, settings, strategies as st

from app.services.generation import ops as ops_mod
from app.services.generation import beat
from app.services.generation import fingerprint as fp_utils
from app.services.team import intention

SECTIONS = [{"index": i, "name": n} for i, n in enumerate(["intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro"])]


def test_their_own_words_decide_the_lean():
    assert intention.song_lean(["a quiet, hushed song for my grandmother"], 0.9) == -1
    assert intention.song_lean(["a big driving anthem"], 0.2) == 1
    assert intention.song_lean([""], 0.2) == -1 and intention.song_lean([""], 0.5) == 0


def test_only_a_wide_change_counts():
    assert intention.request_pull([{"op": "bigger"}], 8) == 1
    assert intention.request_pull([{"op": "bigger", "section": 2}], 8) == 0          # one section is a detail
    assert intention.request_pull([{"op": "sparser", "part": "drums", "section": [1, 3, 5, 6]}], 8) == -1
    assert intention.request_pull([{"op": "bigger"}, {"op": "smaller"}], 8) == 0


@settings(max_examples=200, deadline=None)
@given(st.sampled_from([1, -1]), st.lists(st.sampled_from(["bigger", "busier", "smaller", "sparser"]), min_size=1, max_size=3))
def test_three_directions_are_real_and_the_first_is_exactly_what_they_asked(pull, kinds):
    asked = [{"op": k, **({"part": "drums"} if k in ("busier", "sparser") else {})} for k in kinds]
    dirs = intention.three_directions(asked, SECTIONS, pull)
    assert dirs[0]["operations"] == asked and len(dirs) == 3
    plan, fp = beat.build_beat_plan(fp_utils.normalize({"tempo_bpm": 90, "energy_level": 0.5, "density": 0.5}))
    for s in plan:
        s.uid = s.index
    for d in dirs[1:]:
        try:
            ops_mod.apply_operations(plan, 1, d["operations"])
        except ops_mod.OpError as exc:
            assert "already" in str(exc) or "isn't playing" in str(exc) or "no drums" in str(exc), exc
    msg = intention.message("quiet and close", pull, dirs)
    assert msg.count("?") == 1 and "quiet and close" in msg and "1." in msg and "3." in msg


def test_answers_to_the_question():
    assert intention.choice("do it anyway") == 0 and intention.choice("the second one") == 1
    assert intention.choice("the other way please") == 2 and intention.choice("hmm, the bass?") is None


def test_said_once_and_their_call_wins(monkeypatch):
    """The whole exchange: a gentle song, 'make it all bigger' is held and asked once; asking again builds it."""
    decisions: list[SimpleNamespace] = []

    async def list_decisions(pid, limit=50):
        return list(reversed(decisions))

    async def insert_decision(pid, data):
        d = SimpleNamespace(id=str(len(decisions)), chosen_option=None, **{k: v for k, v in data.items() if k != "chosen_option"})
        decisions.append(d)
        return d

    async def words(pid):
        return ["a hushed song for my grandmother"], "a hushed song for my grandmother", 0.3

    class Table:
        def __init__(self):
            self.values = {}

        def update(self, values):
            self.values = values
            return self

        def eq(self, col, val):
            for d in decisions:
                if d.id == val:
                    d.chosen_option = self.values.get("chosen_option")
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    from app.db import client, song as song_db

    monkeypatch.setattr(song_db, "list_decisions", list_decisions)
    monkeypatch.setattr(song_db, "insert_decision", insert_decision)
    monkeypatch.setattr(intention, "_their_words", words)
    monkeypatch.setattr(client, "get_supabase", lambda: SimpleNamespace(table=lambda name: Table()))
    big = [{"op": "bigger"}]
    said, run = asyncio.run(intention.check("p", "make it all bigger", big, SECTIONS))
    assert said and run == [] and "hushed" in said, "held, and said kindly with their own words"
    said, run = asyncio.run(intention.check("p", "make it all bigger", big, SECTIONS))
    assert said is None and run is None, "asking again is insisting: built as asked"
    said, run = asyncio.run(intention.check("p", "make it all bigger again", big, SECTIONS))
    assert said is None, "said once per song, never again"
    small = asyncio.run(intention.check("p", "make the second chorus bigger", [{"op": "bigger", "section": 4}], SECTIONS))
    assert small == (None, None), "a small change is never questioned"


def test_picking_a_direction_runs_it(monkeypatch):
    decisions = [SimpleNamespace(id="d1", chosen_option=None, options=[{"kind": "intention", "pull": 1, "directions": [
        {"title": "Exactly what you asked", "operations": [{"op": "bigger"}]},
        {"title": "only the choruses", "operations": [{"op": "bigger", "section": [2, 4, 6]}]}]}])]

    async def list_decisions(pid, limit=50):
        return decisions

    from app.db import client, song as song_db

    monkeypatch.setattr(song_db, "list_decisions", list_decisions)
    updates = []
    monkeypatch.setattr(client, "get_supabase", lambda: SimpleNamespace(table=lambda n: SimpleNamespace(
        update=lambda v: SimpleNamespace(eq=lambda c, i: SimpleNamespace(execute=lambda: updates.append(v))))))
    said, run = asyncio.run(intention.check("p", "the second one", [], SECTIONS))
    assert said is None and run == [{"op": "bigger", "section": [2, 4, 6]}] and updates
