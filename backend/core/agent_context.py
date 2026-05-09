"""Per-request context for agent tool calls.

Tools like ``generate_image`` run inside the agent loop without access to
the FastAPI request that triggered them. We push the caller's workspace
directory into a ``ContextVar`` before kicking off the stream; tools read
it to decide whether to land their output in the user's workspace (when
set) or fall back to their legacy global path (when unset — e.g. when
the Draw module invokes the same tool directly).

``ContextVar`` is safe under asyncio: every task inherits its own copy,
so concurrent users can't cross-contaminate.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional


# Absolute path to the current agent's workspace directory, or None when
# the caller has no workspace (legacy callers like the Draw module).
current_workspace_dir: ContextVar[Optional[str]] = ContextVar(
    "current_workspace_dir", default=None
)

# ID of the current chat agent, used by legacy tools to construct
# workspace URLs that include the required ``agent_id`` query param.
current_agent_id: ContextVar[Optional[str]] = ContextVar(
    "current_agent_id", default=None
)
