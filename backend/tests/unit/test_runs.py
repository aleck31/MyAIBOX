"""Chat runs outlive the connection that started them (backend/api/runs.py).

Regression: when a phone went to the background its connection died, the server cancelled the turn and Strands
rolled it back, so the reply and the tool calls already paid for were lost ("network error" on return).
"""
from __future__ import annotations

import asyncio

from backend.api.runs import KEEPALIVE_FRAME, RunRegistry


def _err(message: str) -> str:
    return f"ERROR:{message}"


async def _source(n: int, delay: float = 0.01, closed: list | None = None):
    try:
        for i in range(n):
            await asyncio.sleep(delay)
            yield f"e{i}"
    finally:
        if closed is not None:
            closed.append(True)


async def _collect(run, start=0, ping_interval=5.0):
    return [e async for e in run.follow(start, ping_interval) if e != KEEPALIVE_FRAME]


def test_the_reply_keeps_running_when_its_viewer_leaves_and_can_be_collected_again():
    async def scenario():
        runs = RunRegistry()
        run = runs.start(("u", "a"), "r1", _source(5), _err)
        viewer = run.follow(0)
        assert [await viewer.__anext__(), await viewer.__anext__()] == ["e0", "e1"]
        await viewer.aclose()                                   # the phone's connection died

        await asyncio.wait_for(run._task, 2)                    # the reply still completes
        assert run.finished and run.events == [f"e{i}" for i in range(5)]
        assert await _collect(runs.get(("u", "a"), "r1")) == run.events      # the client comes back for it

    asyncio.run(scenario())


def test_a_late_viewer_gets_what_was_missed_and_then_the_live_events():
    async def scenario():
        runs = RunRegistry()
        run = runs.start(("u", "a"), "r1", _source(6, delay=0.05), _err)
        await asyncio.sleep(0.12)                               # a few events already happened
        assert await _collect(run) == [f"e{i}" for i in range(6)]

    asyncio.run(scenario())


def test_stopping_and_replacing_a_run_closes_its_source():
    async def scenario():
        runs, closed = RunRegistry(), []
        first = runs.start(("u", "a"), "r1", _source(1000, closed=closed), _err)
        await asyncio.sleep(0.05)
        second = runs.start(("u", "a"), "r2", _source(2), _err)   # newest message for the same agent wins
        await asyncio.wait_for(first._task, 2)
        assert first.finished and closed == [True]
        assert runs.get(("u", "a"), "r1") is None and runs.get(("u", "a"), "r2") is second

        stopped = []
        third = runs.start(("u", "b"), "r3", _source(1000, closed=stopped), _err)
        await asyncio.sleep(0.05)
        assert runs.cancel(("u", "b"), "r3") and not runs.cancel(("u", "b"), "nope")   # Stop
        await asyncio.wait_for(third._task, 2)
        assert stopped == [True]

    asyncio.run(scenario())


def test_a_run_belongs_to_its_user_and_a_runaway_one_is_stopped():
    async def scenario():
        runs = RunRegistry(max_run_seconds=0.1)
        run = runs.start(("alice", "a"), "r1", _source(1000), _err)
        assert runs.get(("bob", "a"), "r1") is None            # another user cannot read it
        await asyncio.wait_for(run._task, 2)
        assert run.finished and run.events[-1].startswith("ERROR:")

    asyncio.run(scenario())


def test_finished_runs_kept_are_capped_oldest_first():
    async def scenario():
        runs = RunRegistry(max_kept=2)
        for i in range(4):
            run = runs.start(("u", f"slot-{i}"), f"r{i}", _source(1), _err)
            await asyncio.wait_for(run._task, 2)
        runs.start(("u", "slot-x"), "rx", _source(1), _err)     # any new run purges
        kept = [i for i in range(4) if runs.get(("u", f"slot-{i}"), f"r{i}") is not None]
        assert kept == [2, 3]

    asyncio.run(scenario())
