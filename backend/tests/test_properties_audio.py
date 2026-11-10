"""
Property-based tests for Frank's audio invariants and cross-room resolution.

Audio arrays are tiny (a few hundred samples) so hundreds of examples run fast;
the invariants are about shape, length and level, not fidelity.
"""
import io

import numpy as np
import soundfile as sf
from hypothesis import given, settings, strategies as st
from hypothesis.extra import numpy as hnp

from app.services.audio import mixing
from app.services.audio.vocal_resolution import resolve_vocal_url

SR = mixing.SR


def _wav(samples: np.ndarray) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, samples, SR, format="WAV", subtype="FLOAT")
    return buf.getvalue()


mono_audio = hnp.arrays(
    dtype=np.float32,
    shape=st.integers(min_value=1, max_value=3000),
    elements=st.floats(min_value=-1.0, max_value=1.0, width=32),
)


# ── Mix invariants ───────────────────────────────────────────────

@given(mono_audio, mono_audio, mono_audio)
@settings(max_examples=60, deadline=None)
def test_mix_is_at_least_as_long_as_longest_input(v, b, h):
    mix = mixing.render_mix(_wav(v), _wav(b), _wav(h), {})
    assert mix.shape[0] == 2
    assert mix.shape[1] >= max(len(v), len(b), len(h))


@given(mono_audio, mono_audio, st.floats(-12, 12), st.floats(-12, 12))
@settings(max_examples=60, deadline=None)
def test_mix_never_clips_past_headroom(v, b, vgain, bgain):
    mix = mixing.render_mix(
        _wav(v), _wav(b), None, {"vocal_gain_db": vgain, "beat_gain_db": bgain}
    )
    assert float(np.abs(mix).max()) <= 0.97 + 1e-4


@given(mono_audio)
@settings(max_examples=40, deadline=None)
def test_harmony_toggle_off_equals_no_harmony(h):
    v = np.full(500, 0.1, dtype=np.float32)
    off = mixing.render_mix(_wav(v), None, _wav(h), {"harmony_enabled": False})
    none = mixing.render_mix(_wav(v), None, None, {})
    assert off.shape == none.shape
    assert np.allclose(off, none, atol=1e-6)


def test_mix_with_no_layers_is_empty_not_a_crash():
    assert mixing.render_mix(None, None, None, {}).shape == (2, 0)


# ── Section gain: the "fake handoff" regression ──────────────────

section_names = st.sampled_from(["intro", "verse", "chorus", "bridge", "outro"])


@given(
    st.lists(st.tuples(section_names, st.integers(1, 3)), min_size=2, max_size=6),
    st.sampled_from(["intro", "verse", "chorus", "bridge", "outro"]),
    st.floats(min_value=3.0, max_value=12.0),
)
@settings(max_examples=60, deadline=None)
def test_section_gain_changes_only_the_named_sections(layout, target, gain_db):
    """The Spec 06 bug: section gain silently did nothing. Property: sections
    with the named type are scaled by exactly the gain, all others untouched."""
    bpm = 120
    sections = [{"name": n, "bars": b} for n, b in layout]
    samples_per_bar = int(4 * SR * 60.0 / bpm)
    total = sum(b for _, b in layout) * samples_per_bar
    beat = np.full((2, total), 0.1, dtype=np.float32)

    out = mixing._apply_section_gains(beat.copy(), {target: gain_db}, sections, bpm)

    assert out.shape == beat.shape
    factor = 10.0 ** (gain_db / 20.0)
    cursor = 0
    for name, bars in layout:
        length = int(bars * 4 * (SR * 60.0 / bpm))
        window = out[:, cursor : cursor + length]
        expected = 0.1 * (factor if name == target else 1.0)
        assert np.allclose(window, expected, rtol=1e-4)
        cursor += length


# ── Cross-room vocal resolution (voice-to-export-flow R2) ────────

urls = st.text(alphabet="abcdef0123456789", min_size=1, max_size=8).map(
    lambda s: f"https://x/{s}.mp3"
)
takes = st.one_of(
    st.none(),
    st.fixed_dictionaries(
        {"audio_url": urls}, optional={"processed_url": st.one_of(st.none(), urls)}
    ),
)
comps = st.one_of(st.none(), st.fixed_dictionaries({"audio_url": urls}))


@given(comps, takes)
def test_resolution_returns_one_of_the_available_urls_or_none(comp, take):
    result = resolve_vocal_url(comp, take)
    candidates = set()
    if comp:
        candidates.add(comp["audio_url"])
    if take:
        candidates |= {take["audio_url"], take.get("processed_url")}
    assert result is None or result in candidates
    if comp is None and take is None:
        assert result is None


@given(takes)
def test_with_no_comp_the_tuned_take_always_wins(take):
    result = resolve_vocal_url(None, take)
    if take:
        assert result == (take.get("processed_url") or take["audio_url"])


@given(comps, takes)
def test_an_available_vocal_is_never_silently_dropped(comp, take):
    if comp or take:
        assert resolve_vocal_url(comp, take) is not None
