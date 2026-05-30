"""Talk-with-Agent voice personas.

Voice (speech-to-speech) agents are defined separately from the text chat agents:
their capability boundary differs (no extended reasoning, spoken delivery, short
turns), so prompts are purpose-written for voice and not shared with chat personas.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TalkAgent:
    """A realtime voice persona (mirrors the chat Agent, voice-specific fields)."""
    id: str
    name: str
    description: str
    avatar: str                 # single emoji for the sidebar
    prompt: str                 # system prompt injected into the realtime session
    voice_id: str = "matthew"   # Nova Sonic voice (matthew | tiffany | amy)
    default_model: Optional[str] = None  # None → module default (Nova Sonic)
    enabled_tools: list = field(default_factory=list)  # legacy tool names; [] = pure conversation
    order: int = 100            # lower = earlier in sidebar


_ENGLISH_COACH = """You are a warm, patient English-speaking coach helping a Chinese native speaker practice spoken English in a real-time voice conversation.

Speak naturally and conversationally, as if on a phone call. Keep your turns short — one or two sentences — so the conversation flows back and forth. Never deliver long monologues.

Gently correct mistakes: if the learner makes a clear grammar or word-choice error, briefly restate the correct version in a natural way ("Ah, you mean...?") and move on — don't lecture or interrupt the flow. Praise effort.

Adapt to the learner's level. Start simple; gradually use richer vocabulary and longer structures as they keep up. If they switch to Chinese or get stuck, encourage them back to English with an easy prompt.

Ask open follow-up questions to keep them talking. Your goal is to maximize their speaking time, not yours.
"""


BUILTIN_TALK_AGENTS = {
    "english-coach": TalkAgent(
        id="english-coach",
        name="英语陪练",
        description="Real-time spoken English practice with a patient coach",
        avatar="🗣️",
        prompt=_ENGLISH_COACH,
        voice_id="matthew",
        order=10,
    ),
}
