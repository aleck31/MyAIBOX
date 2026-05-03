"""SSO introspect client — caching, negative result, stale-fallback.

The real _call_introspect uses aiohttp; we patch it at the module level so
none of these tests touch the network.
"""
from __future__ import annotations

import pytest

from backend.common import sso


@pytest.fixture(autouse=True)
def _reset_cache():
    sso._cache.clear()
    yield
    sso._cache.clear()


@pytest.fixture
def fake_introspect(monkeypatch):
    """Patch _call_introspect to return / raise whatever the test queues up."""
    calls = []
    queue: list = []

    async def _fake(sid):
        calls.append(sid)
        if not queue:
            raise AssertionError("fake_introspect called but queue empty")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(sso, "_call_introspect", _fake)
    return {"calls": calls, "queue": queue}


def _valid_response(sub: str = "sub-1", username: str = "alice") -> dict:
    return {
        "valid": True,
        "sub": sub,
        "username": username,
        "email": f"{username}@example.com",
        "exp": 9999999999,
    }


async def test_empty_sid_returns_none_without_network(fake_introspect):
    result = await sso.introspect("")
    assert result is None
    assert fake_introspect["calls"] == []


async def test_valid_sid_caches_positive_result(fake_introspect):
    fake_introspect["queue"].append(_valid_response())

    first = await sso.introspect("sid-1")
    second = await sso.introspect("sid-1")

    assert first is not None
    assert first.username == "alice"
    assert first is second  # identical cached instance
    assert fake_introspect["calls"] == ["sid-1"]  # only one network call


async def test_invalid_sid_caches_negative_result(fake_introspect):
    fake_introspect["queue"].append({"valid": False, "reason": "not_found"})

    first = await sso.introspect("sid-bad")
    second = await sso.introspect("sid-bad")

    assert first is None
    assert second is None
    # Negative results should also avoid a hot-loop of network calls within TTL
    assert len(fake_introspect["calls"]) == 1


async def test_stale_cache_used_when_auth_unavailable(fake_introspect, monkeypatch):
    # Shorten TTL so we can simulate 'stale but within grace'
    monkeypatch.setitem(sso._sso_conf, "cache_ttl", 0)
    monkeypatch.setitem(sso._sso_conf, "stale_grace_ttl", 60)

    fake_introspect["queue"].append(_valid_response())
    first = await sso.introspect("sid-ok")
    assert first is not None

    # Now the cache entry is immediately 'stale' but within grace. Fail the network.
    fake_introspect["queue"].append(RuntimeError("auth down"))
    second = await sso.introspect("sid-ok")

    assert second is first  # stale cache returned


async def test_sso_error_raised_when_no_cache_fallback(fake_introspect):
    fake_introspect["queue"].append(RuntimeError("auth down"))

    with pytest.raises(sso.SSOError):
        await sso.introspect("never-seen")


async def test_invalidate_clears_cache(fake_introspect):
    fake_introspect["queue"].append(_valid_response())
    await sso.introspect("sid-1")
    assert "sid-1" in sso._cache

    sso.invalidate("sid-1")
    assert "sid-1" not in sso._cache


def test_build_login_url_encodes_redirect(monkeypatch):
    monkeypatch.setitem(sso._sso_conf, "auth_origin", "https://auth.example.com")
    url = sso.build_login_url("https://app/page?x=1")
    assert url == "https://auth.example.com/login?redirect=https%3A%2F%2Fapp%2Fpage%3Fx%3D1"
