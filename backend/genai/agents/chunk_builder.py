"""
Chunk Builder for Agent Streaming Responses

Utility functions for creating standardized response chunks in streaming mode.
"""
from typing import Dict, Any, Optional


def create_text_chunk(text: str) -> Dict[str, Any]:
    """Create text chunk
    
    Args:
        text: Text content to stream
        
    Returns:
        {"text": str}
    """
    return {"text": text}


def create_thinking_chunk(thinking: str) -> Dict[str, Any]:
    """Create thinking chunk
    
    Args:
        thinking: Thinking/reasoning content
        
    Returns:
        {"thinking": str}
    """
    return {"thinking": thinking}


def create_tool_chunk(
    name: str, 
    params: Dict[str, Any], 
    status: str = "running", 
    result: Optional[str] = None,
    tool_use_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create tool use chunk
    
    Args:
        name: Tool name
        params: Tool parameters as dict
        status: Tool execution status (running|completed|failed)
        result: Tool execution result (optional)
        tool_use_id: Tool use ID for tracking this specific invocation (optional)
        
    Returns:
        {"tool_use": {"name": str, "params": dict, "status": str, "result": str, "tool_use_id": str}}
    """
    chunk = {
        "tool_use": {
            "name": name,
            "params": params,
            "status": status
        }
    }
    if result:
        chunk["tool_use"]["result"] = result
    if tool_use_id:
        chunk["tool_use"]["tool_use_id"] = tool_use_id
    return chunk


def create_file_chunk(
    path: str, 
    file_type: str, 
    language: Optional[str] = None
) -> Dict[str, Any]:
    """Create file chunk
    
    Args:
        path: File path
        file_type: File type (image|audio|video|document|code)
        language: Programming language (for code files)
        
    Returns:
        {"files": [{"path": str, "type": str, "language": str}]}
    """
    file_info = {"path": path, "type": file_type}
    if language:
        file_info["language"] = language
    return {"files": [file_info]}
