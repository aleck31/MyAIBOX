"""
Strands Built-in Tools
Simple builtin tools list containing only verified working tools
"""
import importlib
from typing import List, Optional
from .. import logger


# Only include verified working tools
BUILTIN_TOOLS = [
    'current_time',
    'calculator',
    'http_request',
    'sleep',
    'speak',
    'file_write',
    'file_read',
    'editor',
]


def _import_tool(tool_name: str):
    """Import `strands_tools.<tool_name>` and return the module."""
    return importlib.import_module(f"strands_tools.{tool_name}")


def load_builtin_tools(tool_filter: Optional[List[str]] = None) -> List:
    """Load builtin tools.

    Args:
        tool_filter: Optional list of specific tool names to load.

    Returns:
        List of loaded Strands tool modules.
    """
    tools = []
    tools_to_load = tool_filter if tool_filter else BUILTIN_TOOLS

    for tool_name in tools_to_load:
        if tool_name not in BUILTIN_TOOLS:
            continue
        try:
            tools.append(_import_tool(tool_name))
            logger.debug(f"Loaded Strands tool: {tool_name}")
        except ImportError:
            logger.warning(f"Tool {tool_name} not available")
        except Exception as e:
            logger.error(f"Error loading tool {tool_name}: {e}")

    logger.info(f"Loaded {len(tools)} Strands builtin tools")
    return tools


def get_available_tools() -> List[str]:
    """Return builtin tool names that are importable in this environment."""
    available = []
    for tool_name in BUILTIN_TOOLS:
        try:
            _import_tool(tool_name)
            available.append(tool_name)
        except ImportError:
            pass
    return available
