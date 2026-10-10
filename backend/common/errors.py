"""Errors whose message is safe and useful to show to the end user."""


class ModelUnavailableError(ValueError):
    """The requested model id is not in the registry (retired, removed, or a stale page).

    Subclasses ValueError so existing `except ValueError` handling keeps working. The message is
    written for the user: pages opened before a model was retired keep sending its old id.
    """

    def __init__(self, model_id: str):
        self.model_id = model_id
        super().__init__(
            f"Model '{model_id}' is not available. It may have been retired or removed; "
            "refresh the page and choose another model."
        )


def user_message(exc: BaseException, default: str) -> str:
    """Message to show the user: the exception's own text if it is meant for users, else `default`.

    Everything else stays generic so internal details (stack text, provider errors) never leak.
    """
    return str(exc) if isinstance(exc, ModelUnavailableError) else default
