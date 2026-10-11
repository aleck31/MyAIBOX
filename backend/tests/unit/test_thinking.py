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
    uses_adaptive_thinking,
)


# ── normalize_intent ──────────────────────────────────────────────────────────


def test_normalize_legacy_enabled_derives_effort_from_budget():
    assert normalize_intent({"type": "enabled", "budget_tokens": 4096}) == {"enabled": True, "effort": "high"}


def test_normalize_bad_effort_falls_back_to_default():
    assert normalize_intent({"enabled": True, "effort": "bogus"}) == {"enabled": True, "effort": "high"}


# ── effort ↔ budget ───────────────────────────────────────────────────────────

def test_effort_to_budget_clamps_below_max_tokens():
    # max → 24576, but max_tokens=4096 forces a clamp leaving room for the answer.
    b = effort_to_budget("max", max_tokens=4096)
    assert b < 4096 and b >= 1024


# ── build_thinking_fields ─────────────────────────────────────────────────────

def test_opus_47_uses_adaptive_with_summarized_display():
    fields = build_thinking_fields("global.anthropic.claude-opus-4-7", {"enabled": True, "effort": "high"})
    assert fields["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert fields["output_config"] == {"effort": "high"}
    assert "budget_tokens" not in fields["thinking"]


def test_older_claude_uses_enabled_budget():
    fields = build_thinking_fields("global.anthropic.claude-sonnet-4-6", {"enabled": True, "effort": "high"})
    assert fields["thinking"]["type"] == "enabled"
    assert fields["thinking"]["budget_tokens"] == 8192
    assert "output_config" not in fields


# ── 2026-10 model generation: adaptive-only + sampling restrictions ───────────

import pytest  # noqa: E402



@pytest.mark.parametrize("model_id", ["global.anthropic.claude-opus-5-5", "global.anthropic.claude-sonnet-5-5",
                                      "global.anthropic.claude-haiku-5-5", "global.anthropic.claude-fable-5-1"])
def test_new_claude_generation_is_adaptive_only(model_id):
    assert uses_adaptive_thinking(model_id)
    assert build_thinking_fields(model_id, {"enabled": True, "effort": "high"})["thinking"]["type"] == "adaptive"
