"""
Property-based tests for private-audio URL signing (private-audio spec 2.2, 2.5).

The rewrite must change ONLY values that are entirely a Frank storage URL, keep
the JSON's shape, and never fail the response if signing fails.
"""
from urllib.parse import quote

from hypothesis import given, strategies as st

from app.services.storage.signing import parse_storage_url, sign_json

BASE = "https://proj.supabase.co"
OTHER = "https://evil.example.com"

buckets = st.sampled_from(["vocals", "beats", "mixes", "hums", "voice-memos", "textures", "exports"])
names = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_.", min_size=1, max_size=20)
kinds = st.sampled_from(["public", "sign", "authenticated"])


def url(kind: str, bucket: str, path: str, base: str = BASE) -> str:
    return f"{base}/storage/v1/object/{kind}/{bucket}/{quote(path)}"


def fake_signer(refs):
    return {r: f"SIGNED::{r[0]}/{r[1]}" for r in refs}


def failing_signer(refs):
    raise RuntimeError("storage is down")


# JSON values that are NOT storage URLs
plain = st.one_of(
    st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False),
    st.text(max_size=30),
)
json_values = st.recursive(
    plain,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(st.text(max_size=8), children, max_size=4),
    ),
    max_leaves=15,
)


@given(kinds, buckets, names)
def test_parse_round_trips_bucket_and_path(kind, bucket, path):
    assert parse_storage_url(url(kind, bucket, path), BASE) == (bucket, path)


@given(kinds, buckets, names)
def test_a_query_string_does_not_change_the_reference(kind, bucket, path):
    assert parse_storage_url(url(kind, bucket, path) + "?token=abc&x=1", BASE) == (bucket, path)


@given(kinds, buckets, names)
def test_urls_on_other_hosts_are_never_ours(kind, bucket, path):
    assert parse_storage_url(url(kind, bucket, path, base=OTHER), BASE) is None


@given(st.text(max_size=60))
def test_arbitrary_text_is_not_a_storage_url(text):
    assert parse_storage_url(text, BASE) is None


@given(json_values)
def test_json_with_no_storage_urls_is_returned_unchanged(data):
    assert sign_json(data, BASE, fake_signer) == data


@given(buckets, names, json_values)
def test_a_storage_url_value_is_replaced_and_the_rest_is_untouched(bucket, path, extra):
    original = url("public", bucket, path)
    data = {"audio_url": original, "other": extra, "nested": [{"render_url": original}]}
    out = sign_json(data, BASE, fake_signer)
    expected = f"SIGNED::{bucket}/{path}"
    assert out["audio_url"] == expected
    assert out["nested"][0]["render_url"] == expected
    assert out["other"] == extra            # everything else identical
    assert set(out) == set(data)            # same keys, same shape


@given(buckets, names, st.text(max_size=20))
def test_prose_that_merely_contains_a_url_is_not_rewritten(bucket, path, words):
    sentence = f"{words} listen at {url('public', bucket, path)} thanks"
    assert sign_json({"message": sentence}, BASE, fake_signer) == {"message": sentence}


@given(buckets, names, json_values)
def test_a_failing_signer_leaves_the_response_exactly_as_it_was(bucket, path, extra):
    data = {"audio_url": url("public", bucket, path), "x": extra}
    assert sign_json(data, BASE, failing_signer) == data


@given(buckets, names)
def test_a_file_the_signer_omits_is_left_as_is(bucket, path):
    data = {"audio_url": url("public", bucket, path)}
    assert sign_json(data, BASE, lambda refs: {}) == data
