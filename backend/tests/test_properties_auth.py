"""
Property-based tests for the auth decisions (auth spec requirements 4.4, 5.2).

These cover the pure rules only. They do not prove the HTTP wiring; that is
checked live against a running server (auth spec task 6.1).
"""
from types import SimpleNamespace

from hypothesis import given, strategies as st

from app.auth import bypass_allowed, owns_project

ids = st.text(alphabet="0123456789abcdef-", min_size=1, max_size=36)
environments = st.sampled_from(
    ["development", "production", "staging", "test", "", "Development", "dev"]
)


@given(ids, ids)
def test_a_project_is_accessible_only_to_its_owner(owner, caller):
    project = {"id": "p", "user_id": owner}
    assert owns_project(project, caller) == (owner == caller)


@given(ids)
def test_a_missing_project_is_never_accessible(caller):
    assert owns_project(None, caller) is False


@given(st.one_of(st.none(), ids))
def test_an_empty_caller_never_owns_anything(owner):
    assert owns_project({"user_id": owner}, "") is False


@given(ids)
def test_a_project_with_no_owner_is_never_accessible(caller):
    assert owns_project({"id": "p"}, caller) is False


@given(environments, st.booleans())
def test_bypass_only_in_development_with_auth_explicitly_off(env, auth_required):
    settings = SimpleNamespace(environment=env, auth_required=auth_required)
    expected = env == "development" and not auth_required
    assert bypass_allowed(settings) is expected


@given(environments.filter(lambda e: e != "development"))
def test_bypass_is_never_allowed_outside_development(env):
    for flag in (True, False):
        assert bypass_allowed(SimpleNamespace(environment=env, auth_required=flag)) is False
