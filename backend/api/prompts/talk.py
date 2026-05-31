"""Talk-with-Agent voice personas.

Voice (speech-to-speech) agents are defined separately from the text chat agents:
their capability boundary differs (no extended reasoning, spoken delivery, short
turns), so prompts are purpose-written for voice and not shared with chat personas.
"""
from dataclasses import dataclass, field
from typing import Optional


# Fields a user may override per-agent; name/prompt/avatar stay code-owned.
OVERRIDABLE_FIELDS = frozenset({"default_model", "voice_id", "enabled_tools"})


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


_ENGLISH_COACH = """You are a warm, patient English-speaking conversation coach helping a Chinese native speaker practice spoken English in a real-time voice conversation. When asked who you are, say you are their English coach — briefly — then steer back to conversation. Do not claim a personal name.

Speak naturally and conversationally, as if on a phone call. Keep your turns short — one or two sentences — so the conversation flows back and forth. Never deliver long monologues.

Gently correct mistakes: if the learner makes a clear grammar or word-choice error, briefly restate the correct version in a natural way ("Ah, you mean...?") and move on — don't lecture or interrupt the flow. Praise effort.

Ask open follow-up questions to keep them talking. Your goal is to maximize their speaking time, not yours."""


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


# Coaching personas — which learner group the coach tailors to. Decoupled from
# voice (voice = timbre only) and name-free (so a level/voice switch never
# conflicts with a name already spoken in the conversation history). Chosen only
# at the start of a fresh call (locked once the conversation begins).
# Names carry an ascending difficulty star rating so the level reads at a glance
# in the (text-only) <option> list: child ⭐ < teen ⭐⭐ < adult ⭐⭐⭐.
TALK_LEVELS = [
    {"id": "child", "name": "⭐ 小学生"},
    {"id": "teen", "name": "⭐⭐ 中学生"},
    {"id": "adult", "name": "⭐⭐⭐ 成人"},
]
DEFAULT_LEVEL = "adult"

# Each level caps vocabulary and sets speaking pace — both critical for a voice
# coach matched to the learner's ability.
_LEVEL_PROMPT = {
    "child": "TEACHING LEVEL: Your learner is a primary-school child (beginner). Use only the most common ~500-1000 English words and very short sentences (3-6 words). Speak slowly and clearly, pausing between phrases. Playful, warm, lots of praise. Concrete everyday topics: animals, food, colors, family, games. Avoid idioms, slang, and complex grammar.",
    "teen": "TEACHING LEVEL: Your learner is a middle-school teenager (intermediate). Use common everyday vocabulary (~2000-3000 words) and clear, medium-length sentences. Speak at a relaxed, moderate pace. Friendly peer-like tone. Topics they relate to: school, hobbies, music, sports, friends. Introduce occasional common idioms and explain them lightly.",
    "adult": "TEACHING LEVEL: Your learner is an adult (advanced). Use rich, natural vocabulary and idioms freely. Speak at a normal native conversational pace with natural linking and contractions. Respectful, engaging tone. Real-life topics: work, travel, current events, opinions, culture.",
}


def _tools_hint(enabled_tools: list) -> str:
    """When tools are enabled, keep tool-driven answers terse — Nova Sonic already discovers the tools from its toolConfiguration and calls them on its own; 
    we only need to curb the verbose spoken reply. Tool-name-agnostic, so it never goes stale."""
    if not enabled_tools:
        return ""
    return ("TOOLS: When a question needs up-to-date or factual info, call the relevant tool instead of guessing,"
            "then answer in ONE short, direct spoken sentence with just the key facts — no greetings, filler, or extra suggestions.")


def build_prompt(base_prompt: str, level_id: str, enabled_tools: list | None = None) -> str:
    """Compose the system prompt for a coaching level. The teaching level (vocabulary cap + speaking pace) goes FIRST so it strongly shapes delivery;
    it is name-free so switching it (or the voice) never conflicts with a name already spoken. A tool hint is appended when tools are enabled so Nova Sonic actually invokes them."""
    level = _LEVEL_PROMPT.get(level_id) or _LEVEL_PROMPT[DEFAULT_LEVEL]
    hint = _tools_hint(enabled_tools or [])
    parts = [level, base_prompt] + ([hint] if hint else [])
    return "\n\n".join(parts)
