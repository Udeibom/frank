"""
Property-based tests for job reliability (job-reliability spec 1.1, 2.1, 2.3).
Pure logic only; the database writes are verified live.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from hypothesis import given, strategies as st

from app.services.jobs.staleness import (
    ACTIVE_STATUSES,
    STALE_AFTER,
    is_stale,
    parse_timestamp,
    with_retries,
)

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
ages = st.timedeltas(min_value=timedelta(0), max_value=timedelta(days=3))
statuses = st.sampled_from(["pending", "processing", "complete", "failed"])


def job(status: str, age: timedelta, fmt: str = "iso") -> dict:
    ts = NOW - age
    value = {
        "iso": ts.isoformat(),
        "z": ts.isoformat().replace("+00:00", "Z"),
        "datetime": ts,
    }[fmt]
    return {"status": status, "updated_at": value}


@given(statuses, ages)
def test_stale_iff_active_and_older_than_the_limit(status, age):
    expected = status in ACTIVE_STATUSES and age > STALE_AFTER
    assert is_stale(job(status, age), NOW) is expected


@given(st.sampled_from(["complete", "failed"]), ages)
def test_finished_jobs_are_never_stale(status, age):
    assert is_stale(job(status, age), NOW) is False


@given(statuses, ages, st.sampled_from(["iso", "z", "datetime"]))
def test_timestamp_format_does_not_change_the_answer(status, age, fmt):
    assert is_stale(job(status, age, fmt), NOW) == is_stale(job(status, age), NOW)


@given(st.sampled_from(list(ACTIVE_STATUSES)),
       st.one_of(st.none(), st.text(max_size=12), st.integers()))
def test_an_unreadable_timestamp_is_never_called_stale(status, junk):
    if isinstance(junk, str) and parse_timestamp(junk) is not None:
        return  # Hypothesis happened to generate a real timestamp
    assert is_stale({"status": status, "updated_at": junk}, NOW) is False


@given(st.timedeltas(min_value=timedelta(hours=-12), max_value=timedelta(hours=12)))
def test_offsets_are_normalised_to_utc(offset):
    tz = timezone(offset)
    local = (NOW - timedelta(minutes=11)).astimezone(tz)
    assert parse_timestamp(local.isoformat()) == NOW - timedelta(minutes=11)


def _run(coro):
    return asyncio.run(coro)


async def _no_sleep(_: float) -> None:
    return None


@given(st.integers(min_value=1, max_value=6), st.integers(min_value=0, max_value=8))
def test_retries_succeed_iff_failures_fewer_than_attempts(attempts, failures):
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] <= failures:
            raise ConnectionError("blip")
        return "ok"

    try:
        result = _run(with_retries(flaky, attempts=attempts, sleep=_no_sleep))
        assert failures < attempts and result == "ok"
        assert calls["n"] == failures + 1          # stops as soon as it works
    except ConnectionError:
        assert failures >= attempts
        assert calls["n"] == attempts              # never tries more than allowed
