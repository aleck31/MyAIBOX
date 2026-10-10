"""Guard rails for the Strands agent loop.

Strands has no cap on how many model calls one invocation may make. A model that keeps
re-calling a tool (observed: GLM 5.3 + the built-in `calculator`) loops until Python's
recursion limit, ~4 minutes later, holding the connection the whole time.
"""
import os

from strands.hooks import BeforeInvocationEvent, BeforeModelCallEvent, HookProvider, HookRegistry

from backend.common.logger import logger

DEFAULT_MAX_CYCLES = 90  # model calls per user message; a tool round trip is 2-4, long agentic runs tens


def max_cycles_from_env() -> int:
    """`AGENT_MAX_CYCLES`, falling back to the default when unset or not a positive integer."""
    raw = os.getenv("AGENT_MAX_CYCLES", "")
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_CYCLES
    return value if value > 0 else DEFAULT_MAX_CYCLES


class CycleLimit(HookProvider):
    """Ends an invocation cleanly once the model has been called `max_calls` times.

    Cancelling `BeforeModelCallEvent` makes Strands finish the turn with an assistant message
    instead of raising, so the user sees why it stopped and the history stays well-formed.
    """

    def __init__(self, max_calls: int, model_id: str = ""):
        self.max_calls = max_calls
        self.model_id = model_id
        self._calls = 0
        self.stop_message: str | None = None  # set when the cap ended the current turn

    @property
    def message(self) -> str:
        return (
            f"Stopped after {self.max_calls} model calls without reaching an answer. "
            "Try rephrasing or simplifying the request, or switch to another model."
        )

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeInvocationEvent, self._reset)
        registry.add_callback(BeforeModelCallEvent, self._count)

    def _reset(self, event: BeforeInvocationEvent) -> None:
        self._calls = 0
        self.stop_message = None

    def _count(self, event: BeforeModelCallEvent) -> None:
        self._calls += 1
        if self._calls > self.max_calls:
            logger.warning(f"[CycleLimit] {self.model_id or 'agent'} hit {self.max_calls} model calls in one turn; stopping")
            self.stop_message = self.message
            event.cancel = self.message
