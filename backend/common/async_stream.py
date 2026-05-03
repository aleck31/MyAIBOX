"""Adapt a blocking sync iterator into an async iterator.

FastAPI SSE endpoints (`async def event_stream` → `StreamingResponse`) must
hand control back to the event loop between yields — otherwise uvicorn
cannot flush buffered bytes to the socket, and the client sees nothing
until the whole stream completes.

Our LLM providers (`generate_stream`) are contractually *synchronous*
iterators over blocking boto3/SDK calls. Iterating them with a plain
`for` inside an async generator pins the loop for the full duration.

`aiter_sync` runs `next(it)` in the default thread-pool executor, so
each item round-trips through the loop and the enclosing async generator
can `yield` between items. Exceptions and `StopIteration` are preserved.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Iterator, TypeVar, cast

T = TypeVar("T")


class _Stop:
    pass


_STOP = _Stop()


async def aiter_sync(it: Iterator[T]) -> AsyncIterator[T]:
    loop = asyncio.get_running_loop()

    def _next() -> T | _Stop:
        try:
            return next(it)
        except StopIteration:
            return _STOP

    while True:
        item = await loop.run_in_executor(None, _next)
        if isinstance(item, _Stop):
            return
        yield cast(T, item)
