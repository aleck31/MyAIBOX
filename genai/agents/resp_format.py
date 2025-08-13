"""
Agent Provider Standard Response Format
"""
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field


@dataclass
class AgentFileInfo:
    """File information in agent response"""
    path: str
    type: str  # image|audio|document|code
    language: Optional[str] = None  # for code files
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"path": self.path, "type": self.type}
        if self.language:
            result["language"] = self.language
        return result


@dataclass
class AgentToolUse:
    """Tool usage information"""
    name: str
    params: Dict[str, Any]
    status: str = "running"  # running|completed|failed
    result: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "params": self.params,
            "status": self.status
        }
        if self.result:
            result["result"] = self.result
        return result


@dataclass
class AgentResponse:
    """Standard agent response format - used by AgentProvider"""
    text: Optional[str] = None
    thinking: Optional[str] = None
    tool_use: Optional[AgentToolUse] = None
    files: List[AgentFileInfo] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for streaming"""
        result = {}
        
        if self.text is not None:
            result["text"] = self.text
        if self.thinking is not None:
            result["thinking"] = self.thinking
        if self.tool_use is not None:
            result["tool_use"] = self.tool_use.to_dict()
        if self.files:
            result["files"] = [f.to_dict() for f in self.files]
        if self.metadata:
            result["metadata"] = self.metadata
            
        return result
    
    def add_file(self, path: str, file_type: str, language: str = None) -> None:
        """Add file to response"""
        self.files.append(AgentFileInfo(path=path, type=file_type, language=language))
    
    def set_tool_use(self, name: str, params: Dict[str, Any], status: str = "running", result: str = None) -> None:
        """Set tool usage information"""
        self.tool_use = AgentToolUse(name=name, params=params, status=status, result=result)


# Utility functions for AgentProvider implementations
def create_text_chunk(text: str) -> Dict[str, Any]:
    """Create text chunk"""
    return AgentResponse(text=text).to_dict()


def create_thinking_chunk(thinking: str) -> Dict[str, Any]:
    """Create thinking chunk"""
    return AgentResponse(thinking=thinking).to_dict()


def create_file_chunk(file_path: str, file_type: str, language: str = None) -> Dict[str, Any]:
    """Create file chunk"""
    response = AgentResponse()
    response.add_file(file_path, file_type, language)
    return response.to_dict()


def create_tool_chunk(tool_name: str, params: Dict[str, Any], status: str = "running", result: str = None) -> Dict[str, Any]:
    """Create tool use chunk"""
    response = AgentResponse()
    response.set_tool_use(tool_name, params, status, result)
    return response.to_dict()
