"""thinking.build_thinking_fields — per-model wire-format translation.

Regression: Opus 4.7+ needs adaptive+effort with display='summarized' (defaults to
'omitted', hiding reasoning); older Claude needs enabled+budget. The module config
stores a single model-agnostic {enabled, effort} intent for both.
"""
from __future__ import annotations

from backend.genai.models.thinking import (
    build_thinking_fields,
    normalize_intent,
    effort_to_budget,
    budget_to_effort,
    uses_adaptive_thinking,
)


# ── normalize_intent ──────────────────────────────────────────────────────────

def test_normalize_new_form():
    assert normalize_intent({"enabled": True, "effort": "high"}) == {"enabled": True, "effort": "high"}


def test_normalize_new_form_disabled_is_none():
    assert normalize_intent({"enabled": False, "effort": "high"}) is None


def test_normalize_legacy_enabled_derives_effort_from_budget():
    assert normalize_intent({"type": "enabled", "budget_tokens": 4096}) == {"enabled": True, "effort": "high"}


def test_normalize_legacy_adaptive():
    assert normalize_intent({"type": "adaptive", "effort": "max"}) == {"enabled": True, "effort": "max"}


def test_normalize_none_and_empty():
    assert normalize_intent(None) is None
    assert normalize_intent({}) is None


def test_normalize_bad_effort_falls_back_to_default():
    assert normalize_intent({"enabled": True, "effort": "bogus"}) == {"enabled": True, "effort": "high"}


# ── effort ↔ budget ───────────────────────────────────────────────────────────

def test_effort_to_budget_clamps_below_max_tokens():
    # max → 24576, but max_tokens=4096 forces a clamp leaving room for the answer.
    b = effort_to_budget("max", max_tokens=4096)
    assert b < 4096 and b >= 1024


def test_budget_to_effort_roundtrip_tiers():
    assert budget_to_effort(1024) == "low"
    assert budget_to_effort(8192) == "xhigh"  # 8192 is the xhigh floor
    assert budget_to_effort(30000) == "max"


# ── build_thinking_fields ─────────────────────────────────────────────────────

def test_opus_47_uses_adaptive_with_summarized_display():
    fields = build_thinking_fields("global.anthropic.claude-opus-4-7", {"enabled": True, "effort": "high"})
    assert fields["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert fields["output_config"] == {"effort": "high"}
    assert "budget_tokens" not in fields["thinking"]


def test_opus_48_uses_adaptive():
    fields = build_thinking_fields("global.anthropic.claude-opus-4-8", {"enabled": True, "effort": "max"})
    assert fields["thinking"]["type"] == "adaptive"
    assert fields["output_config"] == {"effort": "max"}


def test_older_claude_uses_enabled_budget():
    fields = build_thinking_fields("global.anthropic.claude-sonnet-4-6", {"enabled": True, "effort": "high"})
    assert fields["thinking"]["type"] == "enabled"
    assert fields["thinking"]["budget_tokens"] == 8192
    assert "output_config" not in fields


def test_disabled_intent_yields_empty():
    assert build_thinking_fields("global.anthropic.claude-opus-4-7", {"enabled": False}) == {}
    assert build_thinking_fields("global.anthropic.claude-sonnet-4-6", None) == {}


def test_legacy_intent_translated_for_opus_47():
    # Old DDB config {type:enabled, budget:4096} must still drive adaptive on Opus 4.7.
    fields = build_thinking_fields("global.anthropic.claude-opus-4-7", {"type": "enabled", "budget_tokens": 4096})
    assert fields["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert fields["output_config"] == {"effort": "high"}


def test_uses_adaptive_thinking_substring_match():
    assert uses_adaptive_thinking("us.anthropic.claude-opus-4-7-v1:0")
    assert not uses_adaptive_thinking("global.anthropic.claude-sonnet-4-6")
