# Copyright iX.
# SPDX-License-Identifier: MIT-0
"""Extended-thinking wire-format translation.

Module config stores a *model-agnostic* thinking intent — `{enabled, effort}` —
because the same Asking/Chat module can run on different models. The wire format,
however, is model-specific:

  - Opus 4.7+ dropped the legacy `{type:enabled, budget_tokens}` form (it now 400s)
    in favour of `{type:adaptive}` + `output_config.effort`. Adaptive also defaults
    display='omitted' (signature only) — we must opt into 'summarized' to stream the
    reasoning back to the UI.
  - Older reasoning Claude (3.7 / 4 / sonnet-4.6 / haiku-4.5) keep `{type:enabled,
    budget_tokens}`; effort maps onto a token budget.

This module is the single place that owns both the adaptive-only model list and the
effort↔budget mapping, so the two provider paths (bedrock_converse + Strands agent)
stay in sync.
"""
from typing import Dict, Optional

# Models where `adaptive` is the ONLY supported thinking mode — `enabled` 400s here.
# Substring match, so minor suffixes (e.g. claude-opus-4-7-1) still hit.
ADAPTIVE_ONLY = ('claude-opus-4-7', 'claude-opus-4-8')

EFFORT_LEVELS = ('low', 'medium', 'high', 'xhigh', 'max')
DEFAULT_EFFORT = 'high'

# The default intent for a reasoning model with no explicit thinking config. The frontend
# (AgentCard/ModuleCard) mirrors this so the UI's checked/effort state matches actual behaviour.
DEFAULT_INTENT = {'enabled': True, 'effort': DEFAULT_EFFORT}

# effort → budget_tokens for legacy `enabled` models. Bedrock requires
# budget_tokens >= 1024 and < max_tokens (caller clamps against max_tokens).
_EFFORT_TO_BUDGET = {
    'low': 2048,
    'medium': 4096,
    'high': 8192,
    'xhigh': 16384,
    'max': 24576,
}


def uses_adaptive_thinking(model_id: str) -> bool:
    """True if the model only accepts adaptive thinking (Opus 4.7+)."""
    return any(x in model_id for x in ADAPTIVE_ONLY)


def effort_to_budget(effort: str, max_tokens: Optional[int] = None) -> int:
    """Map an effort tier to a legacy budget_tokens, clamped below max_tokens."""
    budget = _EFFORT_TO_BUDGET.get(effort, _EFFORT_TO_BUDGET[DEFAULT_EFFORT])
    if max_tokens and budget >= max_tokens:
        # Leave room for the answer; never go below the API floor of 1024.
        budget = max(1024, max_tokens - 1024)
    return budget


def budget_to_effort(budget_tokens: int) -> str:
    """Reverse map a legacy budget back to an effort tier (for reading old config)."""
    if budget_tokens < 2048:
        return 'low'
    if budget_tokens < 4096:
        return 'medium'
    if budget_tokens < 8192:
        return 'high'
    if budget_tokens < 16384:
        return 'xhigh'
    return 'max'


def normalize_intent(thinking: Optional[Dict]) -> Optional[Dict]:
    """Coerce a stored thinking config into the canonical `{enabled, effort}` intent.

    Accepts both the new form `{enabled, effort}` and the legacy form
    `{type:'enabled', budget_tokens:N}`. Returns None when thinking is absent.
    """
    if not thinking or not isinstance(thinking, dict):
        return None
    # New form already carries `enabled`.
    if 'enabled' in thinking:
        if not thinking.get('enabled'):
            return None
        effort = thinking.get('effort', DEFAULT_EFFORT)
        if effort not in EFFORT_LEVELS:
            effort = DEFAULT_EFFORT
        return {'enabled': True, 'effort': effort}
    # Legacy form: type=='enabled' means on; derive effort from budget.
    if thinking.get('type') == 'enabled':
        return {'enabled': True, 'effort': budget_to_effort(int(thinking.get('budget_tokens', 4096)))}
    if thinking.get('type') == 'adaptive':
        effort = thinking.get('effort', DEFAULT_EFFORT)
        return {'enabled': True, 'effort': effort if effort in EFFORT_LEVELS else DEFAULT_EFFORT}
    return None


def build_thinking_fields(
    model_id: str,
    thinking: Optional[Dict],
    max_tokens: Optional[int] = None,
) -> Dict:
    """Translate a stored thinking intent into Bedrock additionalModelRequestFields.

    Returns {} when thinking is disabled/absent — callers can merge it unconditionally.
    The caller is responsible for only invoking this on reasoning-capable models;
    a non-reasoning model with thinking set still yields fields, but Bedrock ignores
    them, so gating upstream avoids needless request bloat.
    """
    intent = normalize_intent(thinking)
    if not intent:
        return {}

    effort = intent['effort']
    if uses_adaptive_thinking(model_id):
        # display='summarized' is required — adaptive defaults to 'omitted' on Opus 4.7+.
        return {
            'thinking': {'type': 'adaptive', 'display': 'summarized'},
            'output_config': {'effort': effort},
        }
    return {
        'thinking': {
            'type': 'enabled',
            'budget_tokens': effort_to_budget(effort, max_tokens),
        }
    }
