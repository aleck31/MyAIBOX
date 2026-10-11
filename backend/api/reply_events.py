"""AG-UI reasoning/text events for one reply, emitted in an order the client accepts."""
from typing import List

from ag_ui.core import (
    ReasoningMessageContentEvent, ReasoningMessageEndEvent, ReasoningMessageStartEvent,
    TextMessageContentEvent, TextMessageEndEvent, TextMessageStartEvent,
)
from ag_ui.encoder import EventEncoder

_enc = EventEncoder()

class ReplyEvents:
    """AG-UI reasoning/text events for one reply, always in a valid order.

    The client verifies the stream and aborts the run on a bad sequence: reasoning content needs an open
    reasoning message, and nothing may still be open at RUN_FINISHED. Reasoning can appear anywhere in a
    reply (thinking before the text, a tool progress note after it, more thinking after it), so open/close
    is tracked here rather than at every call site.
    """

    def __init__(self, message_id: str, thinking_id: str):
        self._message_id = message_id
        self._thinking_id = thinking_id
        self._reasoning_open = False
        self._text_open = False

    def reasoning(self, delta: str) -> List[str]:
        events = []
        if not self._reasoning_open:
            events.append(_enc.encode(ReasoningMessageStartEvent(message_id=self._thinking_id)))
            self._reasoning_open = True
        events.append(_enc.encode(ReasoningMessageContentEvent(message_id=self._thinking_id, delta=delta)))
        return events

    def text(self, delta: str) -> List[str]:
        events = self._close_reasoning()
        if not self._text_open:
            events.append(_enc.encode(TextMessageStartEvent(message_id=self._message_id, role="assistant")))
            self._text_open = True
        events.append(_enc.encode(TextMessageContentEvent(message_id=self._message_id, delta=delta)))
        return events

    def finish(self) -> List[str]:
        events = self._close_reasoning()
        if self._text_open:
            events.append(_enc.encode(TextMessageEndEvent(message_id=self._message_id)))
            self._text_open = False
        return events

    def _close_reasoning(self) -> List[str]:
        if not self._reasoning_open:
            return []
        self._reasoning_open = False
        return [_enc.encode(ReasoningMessageEndEvent(message_id=self._thinking_id))]

