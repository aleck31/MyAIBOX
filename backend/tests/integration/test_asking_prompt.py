"""The Asking system prompt must not trip the provider's content filter (real call).

Regression: a line asking the model to "show your complete reasoning pathway" made Claude Sonnet/Opus 5.5 end every
Asking reply with stop_reason=content_filtered and no text.
"""
import pytest

from backend.api import asking
from backend.genai.models import LLMMessage

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("model_id", ["global.anthropic.claude-sonnet-5-5", "global.anthropic.claude-opus-5-5"])
def test_an_everyday_question_is_answered(model_id):
    # An everyday question that needs some thought: with the old prompt it was blocked, "17 x 23" was not.
    provider = asking._get_provider(model_id)
    text = ""
    for chunk in provider.generate_stream(messages=[LLMMessage(role="user", content={"text": "推荐一款适合上班族的早餐"})],
                                          system_prompt=asking.SYSTEM_PROMPT):
        text += (chunk.get("content") or {}).get("text", "") or ""
    assert text.strip() and "content filter" not in text
