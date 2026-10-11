"""AgentService cache eviction and shutdown_all behavior.

Uses a FakeProvider stand-in so we don't touch Strands / LLMs / MCP.
"""
from __future__ import annotations

import time

import pytest

from backend.core.service import agent_service as agent_service_module
from backend.core.service.agent_service import AgentService, shutdown_all


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
