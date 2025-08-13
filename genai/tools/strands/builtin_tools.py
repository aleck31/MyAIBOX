"""
Strands Built-in Tools
简单的内置工具列表，只包含验证可用的工具
"""
from typing import List, Optional
from core.logger import logger


# 只包含验证可用的工具
BUILTIN_TOOLS = [
    'current_time',    # ✅ 已验证工作
    'calculator',      # ✅ 已验证工作  
    'http_request',    # ⚠️ 部分工作
    'sleep',           # ✅ 基础工具
    'speak'            # ✅ 已验证工作，能生成音频文件
]


def load_builtin_tools(tool_filter: Optional[List[str]] = None) -> List:
    """加载内置工具"""
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
    """获取可用的工具列表"""
    available = []
    for tool_name in BUILTIN_TOOLS:
        try:
            exec(f"from strands_tools import {tool_name}")
            available.append(tool_name)
        except ImportError:
            pass
    return available
