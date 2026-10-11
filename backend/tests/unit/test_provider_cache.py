"""ProviderCache — key must include inference params, not just model_id.

Regression: Settings changes to max_tokens/temperature used to require a
restart because the cache hit on model_id alone.
"""
from __future__ import annotations

from backend.common.provider_cache import ProviderCache


class _Counter:
    """Factory that records how many times it was invoked."""
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return f"provider-{self.n}"


def test_same_model_different_params_rebuilds():
    cache = ProviderCache()
    factory = _Counter()
    a = cache.get_or_create("m1", {"max_tokens": 100}, factory)
    b = cache.get_or_create("m1", {"max_tokens": 200}, factory)
    assert a != b
    assert factory.n == 2


def test_nested_list_and_dict_values_are_hashable():
    """Regression: params like {stop_sequences: [...], thinking: {...}}
    used to raise TypeError: unhashable type: 'list'."""
    cache = ProviderCache()
    factory = _Counter()
    params = {
        "stop_sequences": ["end_turn"],
        "thinking": {"type": "enabled", "budget_tokens": 4096},
        "temperature": 1.0,
    }
    a = cache.get_or_create("m1", params, factory)
    b = cache.get_or_create("m1", params, factory)
    assert a == b
    assert factory.n == 1
