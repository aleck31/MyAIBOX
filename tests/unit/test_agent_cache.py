"""AgentService cache eviction and shutdown_all behavior.

Uses a FakeProvider stand-in so we don't touch Strands / LLMs / MCP.
"""
from __future__ import annotations

import time

import pytest

from core.service import agent_service as agent_service_module
from core.service.agent_service import AgentService, shutdown_all


class FakeProvider:
    def __init__(self, model_id: str = "fake-model"):
        self.model_id = model_id
        self.destroyed = False
        self.messages = []

    def destroy(self):
        self.destroyed = True


@pytest.fixture
def svc():
    return AgentService(module_name="test")


def test_cache_eviction_when_at_capacity(svc, monkeypatch):
    monkeypatch.setattr(agent_service_module, "_AGENT_MAX", 3)

    providers = [FakeProvider() for _ in range(4)]
    for i, p in enumerate(providers):
        svc._cache_provider(f"sid-{i}", p)
        # Artificial stagger so LRU timestamps differ deterministically
        time.sleep(0.001)

    assert len(svc._agent_cache) == 3
    # The first one inserted should have been evicted and destroyed
    assert providers[0].destroyed is True
    assert "sid-0" not in svc._agent_cache
    # Later inserts still present
    for i in range(1, 4):
        assert f"sid-{i}" in svc._agent_cache


def test_cache_get_refreshes_timestamp(svc):
    p = FakeProvider()
    svc._cache_provider("sid-1", p)
    ts_before = svc._agent_cache["sid-1"][1]
    time.sleep(0.01)

    result = svc._get_cached_provider("sid-1")

    assert result is p
    assert svc._agent_cache["sid-1"][1] > ts_before


def test_evict_expired_removes_and_destroys(svc, monkeypatch):
    monkeypatch.setattr(agent_service_module, "_AGENT_TTL", 0.01)

    p = FakeProvider()
    svc._cache_provider("stale", p)
    time.sleep(0.02)
    svc._evict_expired()

    assert "stale" not in svc._agent_cache
    assert p.destroyed is True


def test_shutdown_all_destroys_every_cached_provider():
    svc_a = AgentService(module_name="a")
    svc_b = AgentService(module_name="b")
    providers = [FakeProvider() for _ in range(3)]
    svc_a._cache_provider("s1", providers[0])
    svc_a._cache_provider("s2", providers[1])
    svc_b._cache_provider("s3", providers[2])

    shutdown_all()

    for p in providers:
        assert p.destroyed is True
    assert svc_a._agent_cache == {}
    assert svc_b._agent_cache == {}
