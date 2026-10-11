"""Errors whose message is safe and useful to show to the end user."""

# Machine-readable code sent with RUN_ERROR so the client can recover (refresh its model list).
MODEL_UNAVAILABLE = "model_unavailable"


class ModelUnavailableError(ValueError):
    """The requested model id is not in the registry (retired, removed, or a stale page).

    Subclasses ValueError so existing `except ValueError` handling keeps working. The message is
    written for the user: pages opened before a model was retired keep sending its old id.
    """

    def __init__(self, model_id: str):
        self.model_id = model_id
        super().__init__(
            f"Model '{model_id}' is no longer available (retired or removed). "
            "Please choose another model and try again."
        )


# Stop reasons that mean the provider cut the reply off by policy. The stream just ends, usually with no text at
# all, so the user is left looking at a half-written answer unless we say what happened.
BLOCKED_STOP_REASONS = ("content_filtered", "guardrail_intervened")


def blocked_reply_notice(stop_reason: object) -> str:
    """User-facing sentence for a reply the provider blocked; empty string for any other stop reason."""
    if stop_reason in BLOCKED_STOP_REASONS:
        return ("The model stopped without finishing: the provider's content filter blocked this response. "
                "Try rephrasing the question, or choose another model.")
    return ""


def user_message(exc: BaseException, default: str) -> str:
    """Message to show the user: the exception's own text if it is meant for users, else `default`.

    Everything else stays generic so internal details (stack text, provider errors) never leak.
    """
    return str(exc) if isinstance(exc, ModelUnavailableError) else default


def run_error_fields(exc: BaseException, default: str) -> dict:
    """Keyword arguments for an AG-UI `RunErrorEvent`: the user-safe message, plus a code the client can act on.

    A stale page keeps sending a retired model id; the code lets it reload the model list on its own
    instead of asking the user to refresh.
    """
    code = MODEL_UNAVAILABLE if isinstance(exc, ModelUnavailableError) else None
    return {"message": user_message(exc, default), "code": code}
