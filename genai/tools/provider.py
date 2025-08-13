"""
Tool Provider for MyAIBOX
Unified management of Python tools and MCP tools for Strands Agents
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from core.logger import logger
from genai.tools.mcp.mcp_server_manager import mcp_server_manager  # MCP server configuration manager
# Delay imports to avoid circular dependencies
# from genai.tools.legacy.tool_registry import legacy_tool_registry  # Python tool registry


class ToolType(Enum):
    """Tool type enumeration"""
    LEGACY = "legacy"
    MCP = "mcp"
    STRANDS = "strands"


@dataclass
class ToolInfo:
    """Simplified tool information container"""
    name: str
    type: ToolType
    description: str
    enabled: bool = True


class ToolProvider:
    """Unified tool provider"""
    
    def __init__(self):
        # Lazy loading to avoid circular imports
        self._legacy_registry = None
        self._mcp_manager = None
        self._mcp_clients: Dict[str, Any] = {}
        self._initialized = False
    
    @property
    def legacy_registry(self):
        """Lazy load legacy tool registry"""
        if self._legacy_registry is None:
            # Import dynamically to avoid circular imports
            from genai.tools.legacy.tool_registry import legacy_tool_registry
            self._legacy_registry = legacy_tool_registry
        return self._legacy_registry
    
    @property
    def mcp_manager(self):
        """Lazy load MCP server manager"""
        if self._mcp_manager is None:
            self._mcp_manager = mcp_server_manager
        return self._mcp_manager
    
    async def initialize(self):
        """Initialize MCP clients only (legacy tools are already loaded)"""
        if self._initialized:
            return
        
        logger.info("[ToolProvider] Initializing MCP clients...")
        
        try:
            # Initialize MCP clients
            mcp_servers = self.mcp_manager.get_mcp_servers()
            
            for server_name, server_config in mcp_servers.items():
                if server_config.get("disabled", False):
                    continue
                
                try:
                    mcp_client = await self._create_mcp_client(server_name, server_config)
                    if mcp_client:
                        self._mcp_clients[server_name] = mcp_client
                        logger.debug(f"[ToolProvider] Initialized MCP client: {server_name}")
                except Exception as e:
                    logger.error(f"[ToolProvider] Failed to initialize MCP client {server_name}: {e}")
            
            self._initialized = True
            logger.info(f"[ToolProvider] Initialized with {len(self._mcp_clients)} MCP clients")
            
        except Exception as e:
            logger.error(f"[ToolProvider] Error during initialization: {str(e)}")
            raise
    
    async def _create_mcp_client(self, server_name: str, server_config: Dict) -> Optional[Any]:
        """Create MCP client - delegates to existing manager logic"""
        try:
            # Lazy import to avoid circular dependencies
            from strands.tools.mcp import MCPClient
            
            server_type = self.mcp_manager.get_mcp_server_type(server_config)
            
            if server_type == "stdio":
                from mcp import stdio_client, StdioServerParameters
                return MCPClient(
                    lambda: stdio_client(
                        StdioServerParameters(
                            command=server_config["command"],
                            args=server_config.get("args", []),
                            env=server_config.get("env", {})
                        )
                    )
                )
            elif server_type == "http":
                from mcp.client.streamable_http import streamablehttp_client
                return MCPClient(lambda: streamablehttp_client(server_config["url"]))
            elif server_type == "sse":
                from mcp.client.sse import sse_client
                return MCPClient(lambda: sse_client(server_config["url"]))
            else:
                logger.error(f"[ToolProvider] Unsupported server type: {server_type}")
                return None
                
        except Exception as e:
            logger.error(f"[ToolProvider] Failed to create MCP client for {server_name}: {e}")
            return None
    
    async def get_tools_for_agent(self, 
                                  tool_filter: Optional[List[str]] = None,
                                  include_legacy: bool = True,
                                  include_mcp: bool = True,
                                  include_strands: bool = True) -> List[Callable]:
        """Get tools for Strands Agent"""
        if not self._initialized:
            await self.initialize()
        
        tools = []
        
        # Add legacy tools
        if include_legacy:
            # Lazy import to avoid circular dependencies
            from strands import tool
            
            for tool_name, tool_func in self.legacy_registry.tools.items():
                if tool_filter and tool_name not in tool_filter:
                    continue
                
                # Convert to Strands tool
                strands_tool = tool(tool_func)
                tools.append(strands_tool)
        
        # Add Strands built-in tools
        if include_strands:
            try:
                from genai.tools.strands.builtin_tools import load_builtin_tools
                strands_tools = load_builtin_tools(tool_filter)
                tools.extend(strands_tools)
                logger.debug(f"[ToolProvider] Added {len(strands_tools)} Strands tools")
            except ImportError:
                logger.warning("[ToolProvider] Strands builtin tools not available")
        
        # Add MCP tools
        if include_mcp:
            for server_name, mcp_client in self._mcp_clients.items():
                try:
                    with mcp_client:
                        mcp_tools = mcp_client.list_tools_sync()
                        for mcp_tool in mcp_tools:
                            tool_name_attr = getattr(mcp_tool, 'tool_name', None) or getattr(mcp_tool, 'name', None)
                            if tool_name_attr:
                                full_tool_name = f"{server_name}:{tool_name_attr}"
                                if not tool_filter or full_tool_name in tool_filter:
                                    tools.append(mcp_tool)
                except Exception as e:
                    logger.error(f"[ToolProvider] Error getting tools from {server_name}: {e}")
        
        logger.debug(f"[ToolProvider] Returning {len(tools)} tools for agent")
        return tools
    
    def list_tools(self, tool_type: Optional[ToolType] = None, enabled_only: bool = True) -> List[ToolInfo]:
        """List tools by type with filtering options
        
        Args:
            tool_type: Optional filter by tool type
            enabled_only: Whether to return only enabled tools
            
        Returns:
            List of tool information
        """
        tools = []
        
        # Legacy tools
        for tool_name, tool_func in self.legacy_registry.tools.items():
            description = tool_func.__doc__ or f"Legacy tool: {tool_name}"
            tool_info = ToolInfo(
                name=tool_name,
                type=ToolType.LEGACY,
                description=description.strip()
            )
            tools.append(tool_info)
        
        # MCP tools (if initialized)
        if self._initialized:
            for server_name, mcp_client in self._mcp_clients.items():
                try:
                    # Skip if client session is already running to avoid conflicts
                    if hasattr(mcp_client, '_session') and mcp_client._session and getattr(mcp_client._session, 'is_running', False):
                        logger.debug(f"[ToolProvider] Skipping {server_name} - session already running")
                        continue
                    
                    with mcp_client:
                        mcp_tools = mcp_client.list_tools_sync()
                        for mcp_tool in mcp_tools:
                            tool_name_attr = getattr(mcp_tool, 'tool_name', None) or getattr(mcp_tool, 'name', None)
                            if tool_name_attr:
                                description = getattr(mcp_tool, 'description', f"MCP tool from {server_name}")
                                tool_info = ToolInfo(
                                    name=f"{server_name}:{tool_name_attr}",
                                    type=ToolType.MCP,
                                    description=description
                                )
                                tools.append(tool_info)
                except Exception as e:
                    logger.debug(f"[ToolProvider] Could not list tools from {server_name}: {e}")
                    # Continue with other servers even if one fails
                    continue
        
        # Apply filters
        if tool_type:
            tools = [tool for tool in tools if tool.type == tool_type]
        
        if enabled_only:
            tools = [tool for tool in tools if tool.enabled]
        
        return tools
    
    async def reload_tools(self):
        """Reload all tools (compatibility method for handler_tools.py)"""
        logger.info("[ToolProvider] Reloading all tools...")
        self._mcp_clients.clear()
        self._initialized = False
        await self.initialize()


# Create singleton instance - no immediate initialization to avoid circular imports
tool_provider = ToolProvider()
