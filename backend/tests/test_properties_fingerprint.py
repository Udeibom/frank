"""
Property-based tests for the musical fingerprint.

The fingerprint is built by an LLM, so its input is untrusted: any JSON value can
show up in any field. These properties assert the invariants the rest of the
engine relies on, for ALL inputs rather than hand-picked ones.
"""
from hypothesis import given, settings, strategies as st

from app.services.generation.fingerprint import normalize, texture_cache_key

# Anything json.loads could hand back (Python's json accepts NaN/Infinity too).
json_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(max_size=20),
    st.lists(st.integers(), max_size=3),
)

fingerprints = st.fixed_dictionaries(
    {},
    optional={
        "tempo_bpm": json_scalars,
        "tempo_feel": st.text(max_size=12),
        "key": st.text(max_size=12),
        "energy_level": json_scalars,
        "density": json_scalars,
        "brightness": json_scalars,
        "warmth": json_scalars,
        "genre_proximity": st.lists(st.text(max_size=8), max_size=4),
    },
)


@given(fingerprints)
def test_feel_fields_always_clamped_to_unit_range(fp):
    out = normalize(fp)
    for k in ("energy_level", "density", "brightness", "warmth"):
        assert 0.0 <= out[k] <= 1.0


@given(fingerprints)
def test_tempo_always_within_sane_bounds(fp):
    out = normalize(fp)
    assert isinstance(out["tempo_bpm"], int)
    assert 50 <= out["tempo_bpm"] <= 180


@given(fingerprints)
def test_normalize_is_idempotent(fp):
    once = normalize(fp)
    assert normalize(once) == once


@given(fingerprints)
def test_key_is_never_empty(fp):
    assert normalize(fp)["key"]


@given(fingerprints)
def test_cache_key_is_deterministic(fp):
    assert texture_cache_key(fp) == texture_cache_key(dict(fp))


@given(fingerprints, st.lists(st.text(max_size=8), max_size=4))
def test_cache_key_ignores_fields_that_do_not_shape_the_texture(fp, genres):
    """genre_proximity doesn't change the generated texture, so it mustn't
    change the cache key (otherwise identical textures re-render)."""
    a = texture_cache_key(fp)
    b = texture_cache_key({**fp, "genre_proximity": genres})
    assert a == b


@given(st.floats(allow_nan=True, allow_infinity=True))
def test_any_float_tempo_never_crashes_normalize(bpm):
    """Regression found by property testing: int(float('inf')) raises
    OverflowError, which normalize() did not catch. json.loads accepts
    Infinity, so an LLM reply could trigger it."""
    out = normalize({"tempo_bpm": bpm})
    assert 50 <= out["tempo_bpm"] <= 180
