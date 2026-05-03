"""Module-level LLM provider cache keyed by (model_id, inference params).

The key includes params so that Settings changes to `max_tokens` /
`temperature` / etc. take effect without a server restart. Without this,
the cache would return a stale provider built with the old params.
"""
from __future__ import annotations

from typing import Any, Callable, Dict


def _freeze(v: Any) -> Any:
    """Recursively convert dict/list into hashable tuples."""
    if isinstance(v, dict):
        return tuple(sorted((k, _freeze(val)) for k, val in v.items()))
    if isinstance(v, (list, tuple)):
        return tuple(_freeze(x) for x in v)
    return v


def _params_key(params: Dict[str, Any]) -> tuple:
    """Stable hashable key from a params dict (order-independent).

    Values may contain nested dicts/lists (e.g. `stop_sequences: [...]`,
    `thinking: {type, budget_tokens}`), which aren't hashable on their
    own — freeze them recursively.
    """
    return _freeze(params or {})


class ProviderCache:
    """Per-module provider cache. Not thread-safe by design — FastAPI async
    handlers run in a single event loop; concurrent cache writes are
    harmless (last write wins, both values semantically equal)."""

    def __init__(self) -> None:
        self._cache: Dict[tuple, Any] = {}

    def get_or_create(
        self,
        model_id: str,
        params: Dict[str, Any],
        factory: Callable[[], Any],
    ) -> Any:
        """Return the cached provider, rebuilding if the (model_id, params)
        fingerprint has changed."""
        key = (model_id, _params_key(params))
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]

    def clear(self) -> None:
        self._cache.clear()
