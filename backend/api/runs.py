"""Chat runs that outlive the HTTP request that started them.

A reply used to live exactly as long as its streaming response: when the client's connection died (a phone put
to the background or switched off, a network change) the server cancelled the turn and Strands rolled it back,
so the tool calls and tokens already spent were thrown away and the user saw "network error".

Now the turn runs in a task of its own and appends every event to a buffer. The HTTP response is only a
viewer of that buffer, so a viewer going away changes nothing; a new viewer (the client reconnecting) is
replayed the events from the start and then follows the live ones. A run is stopped on purpose (Stop button,
a newer message for the same agent, the time limit), never by a viewer disconnecting.
"""
import asyncio
import time
from typing import AsyncIterator, Callable, Dict, Optional, Tuple

from backend.common.logger import logger

RunKey = Tuple[str, str]  # (user sub, agent id): one run per user and agent at a time

# SSE comment that proxies and browsers ignore, sent while a viewer is idle. CloudFront's idle timeout is the
# binding constraint (default 30s, max 60s); 15s gives a 2x safety margin.
KEEPALIVE_INTERVAL = 15.0
KEEPALIVE_FRAME = b": ping\n\n"


class Run:
    """One reply being produced: the events so far, and whether it has ended."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: list = []
        self.finished = False
        self.finished_at = 0.0
        self._changed = asyncio.Condition()
        self._task: Optional[asyncio.Task] = None

    async def _append(self, event) -> None:
        async with self._changed:
            self.events.append(event)
            self._changed.notify_all()

    async def _finish(self) -> None:
        async with self._changed:
            self.finished = True
            self.finished_at = time.monotonic()
            self._changed.notify_all()

    async def follow(self, start: int = 0, ping_interval: float = KEEPALIVE_INTERVAL) -> AsyncIterator:
        """Yield the events from `start`, then new ones as they arrive, until the run has ended.

        Idle for `ping_interval` seconds yields a keep-alive frame. Closing this generator (the viewer left)
        does not touch the run.
        """
        index = start
        while True:
            async with self._changed:
                if index >= len(self.events) and not self.finished:
                    try:
                        await asyncio.wait_for(self._changed.wait(), ping_interval)
                    except asyncio.TimeoutError:
                        pass
                batch = self.events[index:]
                finished = self.finished
            if batch:
                index += len(batch)
                for event in batch:
                    yield event
            elif finished:
                return
            else:
                yield KEEPALIVE_FRAME

    def cancel(self) -> None:
        """Stop producing (the source generator is closed, which releases the agent)."""
        if self._task is not None and not self._task.done():
            self._task.cancel()


class RunRegistry:
    """The latest run of each (user, agent), kept for a while after it ends so a client can still collect it."""

    def __init__(self, keep_seconds: float = 900.0, max_run_seconds: float = 1800.0):
        self._runs: Dict[RunKey, Run] = {}
        self._keep = keep_seconds
        self._max_run = max_run_seconds

    def start(self, key: RunKey, run_id: str, source: AsyncIterator, error_event: Callable[[str], object]) -> Run:
        """Start `source` as the run of `key`; a run still going for the same key is stopped (newest wins)."""
        self._purge()
        if (previous := self._runs.get(key)) is not None and not previous.finished:
            logger.info(f"[Runs] {key[1]}: a new message replaces the run still going ({previous.run_id})")
            previous.cancel()
        run = Run(run_id)
        run._task = asyncio.create_task(self._pump(run, source, error_event))
        self._runs[key] = run
        return run

    def get(self, key: RunKey, run_id: str) -> Optional[Run]:
        self._purge()
        run = self._runs.get(key)
        return run if run is not None and run.run_id == run_id else None

    def cancel(self, key: RunKey, run_id: str) -> bool:
        run = self.get(key, run_id)
        if run is None or run.finished:
            return False
        run.cancel()
        return True

    async def _pump(self, run: Run, source: AsyncIterator, error_event: Callable[[str], object]) -> None:
        try:
            async with asyncio.timeout(self._max_run):
                async for event in source:
                    await run._append(event)
        except asyncio.CancelledError:
            logger.info(f"[Runs] run {run.run_id} stopped")
        except TimeoutError:
            logger.warning(f"[Runs] run {run.run_id} stopped after {self._max_run:.0f}s")
            await run._append(error_event("This reply took too long and was stopped."))
        except Exception as e:  # the source reports its own failures as events; this is a safety net
            logger.error(f"[Runs] run {run.run_id} failed: {e}", exc_info=True)
            await run._append(error_event("An error occurred during streaming."))
        finally:
            aclose = getattr(source, "aclose", None)
            if aclose is not None:
                try:
                    await asyncio.shield(aclose())
                except BaseException:  # noqa: BLE001 - nothing useful to do if closing the source fails
                    pass
            await asyncio.shield(run._finish())

    def _purge(self) -> None:
        now = time.monotonic()
        for key in [k for k, r in self._runs.items() if r.finished and now - r.finished_at > self._keep]:
            del self._runs[key]


runs = RunRegistry()
