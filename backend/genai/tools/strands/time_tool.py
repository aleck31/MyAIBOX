"""`current_time` tool.

Replaces `strands_tools.current_time`, which Strands deprecated (it logs a warning on every call and
becomes an error log in strands-agents-tools 0.9.0, recommending ContextInjector instead). Kept as a
tool with the same name, arguments and output so agents that enable it keep working unchanged.
"""
import os
from datetime import datetime, timezone as _tz
from zoneinfo import ZoneInfo

from strands import tool


@tool
def current_time(timezone: str = None) -> str:
    """
    Get the current time in ISO 8601 format.

    Returns the current date and time (e.g., 2023-04-15T14:32:16.123456+00:00) for the specified
    timezone. If no timezone is provided, the DEFAULT_TIMEZONE environment variable is used
    ('UTC' if not set).

    Args:
        timezone (str, optional): IANA timezone name such as 'UTC', 'US/Pacific', 'Europe/London' or
            'Asia/Shanghai'. Defaults to the DEFAULT_TIMEZONE environment variable ('UTC' if not set).

    Returns:
        str: The current time in ISO 8601 format.

    Raises:
        ValueError: If an invalid timezone is provided.
    """
    name = timezone or os.getenv("DEFAULT_TIMEZONE", "UTC")
    try:
        zone = _tz.utc if name.upper() == "UTC" else ZoneInfo(name)
        return datetime.now(zone).isoformat()
    except Exception as e:
        raise ValueError(f"Error getting current time: {e}") from e
