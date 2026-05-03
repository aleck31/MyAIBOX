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


def test_same_model_same_params_is_cached():
    cache = ProviderCache()
    factory = _Counter()
    a = cache.get_or_create("m1", {"max_tokens": 100}, factory)
    b = cache.get_or_create("m1", {"max_tokens": 100}, factory)
    assert a == b == "provider-1"
    assert factory.n == 1


def test_same_model_different_params_rebuilds():
    cache = ProviderCache()
    factory = _Counter()
    a = cache.get_or_create("m1", {"max_tokens": 100}, factory)
    b = cache.get_or_create("m1", {"max_tokens": 200}, factory)
    assert a != b
    assert factory.n == 2


def test_different_models_cache_separately():
    cache = ProviderCache()
    factory = _Counter()
    a = cache.get_or_create("m1", {"max_tokens": 100}, factory)
    b = cache.get_or_create("m2", {"max_tokens": 100}, factory)
    assert a != b
    assert factory.n == 2


def test_param_order_independent():
    cache = ProviderCache()
    factory = _Counter()
    a = cache.get_or_create("m1", {"max_tokens": 100, "temperature": 0.7}, factory)
    b = cache.get_or_create("m1", {"temperature": 0.7, "max_tokens": 100}, factory)
    assert a == b
    assert factory.n == 1


def test_empty_params_is_distinct_from_any_params():
    cache = ProviderCache()
    factory = _Counter()
    a = cache.get_or_create("m1", {}, factory)
    b = cache.get_or_create("m1", {"max_tokens": 100}, factory)
    assert a != b
    assert factory.n == 2


def test_none_params_treated_as_empty():
    cache = ProviderCache()
    factory = _Counter()
    a = cache.get_or_create("m1", {}, factory)
    b = cache.get_or_create("m1", None, factory)  # type: ignore[arg-type]
    assert a == b
    assert factory.n == 1


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


def test_nested_values_differ_rebuilds():
    cache = ProviderCache()
    factory = _Counter()
    a = cache.get_or_create("m1", {"stop_sequences": ["a"]}, factory)
    b = cache.get_or_create("m1", {"stop_sequences": ["b"]}, factory)
    assert a != b
    assert factory.n == 2


def test_clear_drops_all_entries():
    cache = ProviderCache()
    factory = _Counter()
    cache.get_or_create("m1", {"t": 1}, factory)
    cache.clear()
    cache.get_or_create("m1", {"t": 1}, factory)
    assert factory.n == 2
