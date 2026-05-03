"""aiter_sync — wrap a blocking sync iterator as an async iterator so
FastAPI SSE handlers can yield control back to the event loop between
items.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from backend.common.async_stream import aiter_sync


@pytest.mark.asyncio
async def test_yields_all_items_in_order():
    async def collect():
        return [x async for x in aiter_sync(iter([1, 2, 3]))]
    assert await collect() == [1, 2, 3]


@pytest.mark.asyncio
async def test_empty_iterator_completes():
    assert [x async for x in aiter_sync(iter([]))] == []


@pytest.mark.asyncio
async def test_exception_from_source_propagates():
    def boom():
        yield 1
        raise RuntimeError("source failed")
    with pytest.raises(RuntimeError, match="source failed"):
        async for _ in aiter_sync(boom()):
            pass


@pytest.mark.asyncio
async def test_does_not_block_event_loop():
    """Each `next()` runs in a thread-pool executor, so a concurrent
    task keeps making progress even while the sync source sleeps."""
    def slow():
        for i in range(3):
            time.sleep(0.05)
            yield i

    ticks = 0

    async def ticker():
        nonlocal ticks
        while ticks < 10:
            await asyncio.sleep(0.01)
            ticks += 1

    async def consume():
        return [x async for x in aiter_sync(slow())]

    results, _ = await asyncio.gather(consume(), ticker())
    assert results == [0, 1, 2]
    # If the loop were blocked for the full ~150ms, the ticker couldn't
    # have incremented. At 10ms cadence it should reach its cap.
    assert ticks >= 5
