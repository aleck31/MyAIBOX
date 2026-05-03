"""
Strands Built-in Tools
Simple builtin tools list containing only verified working tools
"""
from typing import List, Optional
from .. import logger


# Only include verified working tools
BUILTIN_TOOLS = [
    'current_time',
    'calculator',
    'http_request',
    'sleep',
    'speak' 
]


def load_builtin_tools(tool_filter: Optional[List[str]] = None) -> List:
    """Load builtin tools
    
    Args:
        tool_filter: Optional list of specific tool names to load
        
    Returns:
        List of loaded Strands tool functions
    """
    tools = []
    tools_to_load = tool_filter if tool_filter else BUILTIN_TOOLS
    
    for tool_name in tools_to_load:
        if tool_name not in BUILTIN_TOOLS:
            continue
            
        try:
            exec(f"from strands_tools import {tool_name}")
            tool_func = locals()[tool_name]
            tools.append(tool_func)
            logger.debug(f"Loaded Strands tool: {tool_name}")
        except ImportError:
            logger.warning(f"Tool {tool_name} not available")
        except Exception as e:
            logger.error(f"Error loading tool {tool_name}: {e}")
    
    logger.info(f"Loaded {len(tools)} Strands builtin tools")
    return tools


def get_available_tools() -> List[str]:
    """Get list of available tools
    
    Returns:
        List of available tool names
    """
    available = []
    for tool_name in BUILTIN_TOOLS:
        try:
            exec(f"from strands_tools import {tool_name}")
            available.append(tool_name)
        except ImportError:
            pass
    return available
