"""
Tool Provider for MyAIBOX
Unified management of Python tools and MCP tools for Strands Agents
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
from strands import tool
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from mcp import stdio_client, StdioServerParameters
from core.logger import logger
from genai.tools.mcp.mcp_server_manager import mcp_server_manager  # MCP server configuration manager
from genai.tools.legacy.tool_registry import br_registry  # Python tool registry


class ToolType(Enum):
    """Tool type enumeration"""
    LEGACY = "legacy"
    MCP = "mcp"


@dataclass
class ToolInfo:
    """Tool information container"""
    name: str
    type: ToolType
    description: str
    enabled: bool = True
    config: Optional[Dict[str, Any]] = None
    function: Optional[Callable] = None
    mcp_client: Optional[MCPClient] = None


class BaseToolProvider(ABC):
    """Base class for tool providers"""
    
    @abstractmethod
    async def load_tools(self) -> List[ToolInfo]:
        """Load tools from this provider"""
        pass
    
    @abstractmethod
    async def get_tool_function(self, tool_name: str) -> Optional[Callable]:
        """Get executable function for a tool"""
        pass


class LegacyToolProvider(BaseToolProvider):
    """Legacy tool((Python tool) provider - leverages existing BedrockToolRegistry"""
    
    def __init__(self):
        self.tools: Dict[str, ToolInfo] = {}
        self.registry = br_registry  # Use existing registry
    
    async def load_tools(self) -> List[ToolInfo]:
        """Load Python tools from existing BedrockToolRegistry"""
        loaded_tools = []
        
        # Get registered tools from existing registry
        for tool_name, tool_func in self.registry.tools.items():
            try:
                # Convert existing tool function to Strands tool
                strands_tool = tool(tool_func)
                
                # Get tool description
                description = tool_func.__doc__ or f"Python tool: {tool_name}"
                
                # Get tool specification (if exists)
                tool_spec = self.registry.get_tool_spec(tool_name)
                
                tool_info = ToolInfo(
                    name=tool_name,
                    type=ToolType.LEGACY,
                    description=description.strip(),
                    function=strands_tool,
                    config={
                        "original_function": tool_func,
                        "tool_spec": tool_spec,
                        "package": self._get_package_for_tool(tool_name)
                    }
                )
                
                self.tools[tool_name] = tool_info
                loaded_tools.append(tool_info)
                logger.debug(f"[LegacyToolProvider] Loaded tool: {tool_name}")
                
            except Exception as e:
                logger.error(f"[LegacyToolProvider] Error loading tool {tool_name}: {str(e)}")
        
        return loaded_tools
    
    def _get_package_for_tool(self, tool_name: str) -> Optional[str]:
        """Get package name for a tool from the registry's tool_packages mapping"""
        return self.registry.tool_packages.get(tool_name)
    
    async def get_tool_function(self, tool_name: str) -> Optional[Callable]:
        """Get executable function for a Python tool"""
        tool_info = self.tools.get(tool_name)
        return tool_info.function if tool_info else None
    
    async def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute Python tool (compatibility method)"""
        return await self.registry.execute_tool(tool_name, **kwargs)


class MCPToolProvider(BaseToolProvider):
    """MCP tool provider - leverages existing MCP Server Manager"""
    
    def __init__(self):
        self.mcp_clients: Dict[str, MCPClient] = {}
        self.tools: Dict[str, ToolInfo] = {}
        self.mcp_manager = mcp_server_manager  # Use MCP server manager
    
    async def load_tools(self) -> List[ToolInfo]:
        """Load MCP tools from existing ToolManager"""
        loaded_tools = []
        
        # Get MCP server configurations
        mcp_servers = self.mcp_manager.get_mcp_servers()
        
        for server_name, server_config in mcp_servers.items():
            if server_config.get("disabled", False):
                logger.info(f"[MCPToolProvider] Skipping disabled server: {server_name}")
                continue
            
            try:
                # Create MCP client
                mcp_client = await self._create_mcp_client(server_name, server_config)
                if not mcp_client:
                    continue
                
                self.mcp_clients[server_name] = mcp_client
                
                # Get tools from MCP server
                try:
                    with mcp_client:
                        tools = mcp_client.list_tools_sync()
                        
                        for tool in tools:
                            # Handle different tool object types
                            tool_name_attr = getattr(tool, 'tool_name', None) or getattr(tool, 'name', None)
                            
                            if not tool_name_attr:
                                logger.warning(f"[MCPToolProvider] Tool from {server_name} has no name attribute, skipping")
                                continue
                                
                            tool_name = f"{server_name}:{tool_name_attr}"
                            
                            # Try to get description from tool_spec or other attributes
                            description = None
                            if hasattr(tool, 'tool_spec') and tool.tool_spec:
                                description = getattr(tool.tool_spec, 'description', None)
                            if not description:
                                description = getattr(tool, 'description', None)
                            if not description:
                                description = f"MCP tool from {server_name}"
                            
                            tool_info = ToolInfo(
                                name=tool_name,
                                type=ToolType.MCP,
                                description=description,
                                mcp_client=mcp_client,
                                config={
                                    "server": server_name,
                                    "original_name": tool_name_attr,
                                    "server_config": server_config,
                                    "tool_object": tool
                                }
                            )
                            
                            self.tools[tool_name] = tool_info
                            loaded_tools.append(tool_info)
                            logger.debug(f"[MCPToolProvider] Loaded MCP tool: {tool_name}")
                        
                        logger.info(f"[MCPToolProvider] Successfully loaded {len(tools)} tools from {server_name}")
                        
                except Exception as tool_error:
                    logger.error(f"[MCPToolProvider] Error getting tools from {server_name}: {str(tool_error)}")
                    # Don't add this client to the cache if it failed
                    if server_name in self.mcp_clients:
                        del self.mcp_clients[server_name]
                    continue
                
            except Exception as e:
                logger.error(f"[MCPToolProvider] Error loading tools from {server_name}: {str(e)}")
        
        return loaded_tools
    
    async def _create_mcp_client(self, server_name: str, server_config: Dict) -> Optional[MCPClient]:
        """Create MCP client based on server configuration"""
        try:
            server_type = self.mcp_manager.get_mcp_server_type(server_config)
            
            if server_type == "stdio":
                # Stdio-based MCP server
                command = server_config["command"]
                args = server_config.get("args", [])
                env = server_config.get("env", {})
                
                return MCPClient(
                    lambda: stdio_client(
                        StdioServerParameters(
                            command=command,
                            args=args,
                            env=env
                        )
                    )
                )
            elif server_type == "http":
                # HTTP-based MCP server (Streamable HTTP)
                url = server_config["url"]
                return MCPClient(
                    lambda: streamablehttp_client(url)
                )
            elif server_type == "sse":
                # SSE-based MCP server
                from mcp.client.sse import sse_client
                url = server_config["url"]
                return MCPClient(
                    lambda: sse_client(url)
                )
            else:
                logger.error(f"[MCPToolProvider] Unsupported server type: {server_type}")
                return None
                
        except Exception as e:
            logger.error(f"[MCPToolProvider] Failed to create MCP client for {server_name}: {str(e)}")
            return None
    
    async def get_tool_function(self, tool_name: str) -> Optional[Callable]:
        """Get executable object for an MCP tool"""
        tool_info = self.tools.get(tool_name)
        if not tool_info or not tool_info.config:
            return None
        
        # For MCP tools, return the tool object
        # Strands Agent will handle execution
        return tool_info.config.get("tool_object")


class ToolProvider:
    """United tool provider for both Legacy(Python) and MCP tools"""
    
    def __init__(self):
        self.legacy_provider = LegacyToolProvider()
        self.mcp_provider = MCPToolProvider()
        self.all_tools: Dict[str, ToolInfo] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize all tool providers"""
        if self._initialized:
            return
        
        logger.info("[UnitedToolProvider] Initializing tool providers...")
        
        try:
            # Load Python tools
            legacy_tools = await self.legacy_provider.load_tools()
            logger.info(f"[UnitedToolProvider] Loaded {len(legacy_tools)} Python tools")
            
            # Load MCP tools
            mcp_tools = await self.mcp_provider.load_tools()
            logger.info(f"[UnitedToolProvider] Loaded {len(mcp_tools)} MCP tools")
            
            # Combine all tools
            for tool_info in legacy_tools + mcp_tools:
                self.all_tools[tool_info.name] = tool_info
            
            self._initialized = True
            logger.info(f"[UnitedToolProvider] Initialized with {len(self.all_tools)} total tools")
            
        except Exception as e:
            logger.error(f"[UnitedToolProvider] Error during initialization: {str(e)}")
            raise
    
    async def get_tools_for_agent(self, 
                                  tool_filter: Optional[List[str]] = None,
                                  include_legacy: bool = True,
                                  include_mcp: bool = True) -> List[Callable]:
        """Get tools for Strands Agent
        
        Args:
            tool_filter: Optional list of specific tool names to include
            include_legacy: Whether to include Python tools
            include_mcp: Whether to include MCP tools
            
        Returns:
            List of tool functions/objects for Strands Agent
        """
        if not self._initialized:
            await self.initialize()
        
        tools = []
        
        for tool_name, tool_info in self.all_tools.items():
            # Apply filters
            if tool_filter and tool_name not in tool_filter:
                continue
            
            if not tool_info.enabled:
                continue
            
            if tool_info.type == ToolType.LEGACY and not include_legacy:
                continue
            
            if tool_info.type == ToolType.MCP and not include_mcp:
                continue
            
            # Get tool function
            if tool_info.type == ToolType.LEGACY:
                tool_func = await self.legacy_provider.get_tool_function(tool_name)
            else:
                tool_func = await self.mcp_provider.get_tool_function(tool_name)
            
            if tool_func:
                tools.append(tool_func)
        
        logger.debug(f"[UnitedToolProvider] Returning {len(tools)} tools for agent")
        return tools
    
    def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """Get information about a specific tool"""
        return self.all_tools.get(tool_name)
    
    def list_tools(self, tool_type: Optional[ToolType] = None, enabled_only: bool = True) -> List[ToolInfo]:
        """List all available tools
        
        Args:
            tool_type: Optional filter by tool type
            enabled_only: Whether to return only enabled tools
            
        Returns:
            List of tool information
        """
        tools = list(self.all_tools.values())
        
        if tool_type:
            tools = [tool for tool in tools if tool.type == tool_type]
        
        if enabled_only:
            tools = [tool for tool in tools if tool.enabled]
        
        return tools
    
    def enable_tool(self, tool_name: str):
        """Enable a specific tool"""
        if tool_name in self.all_tools:
            self.all_tools[tool_name].enabled = True
            logger.info(f"[UnitedToolProvider] Enabled tool: {tool_name}")
    
    def disable_tool(self, tool_name: str):
        """Disable a specific tool"""
        if tool_name in self.all_tools:
            self.all_tools[tool_name].enabled = False
            logger.info(f"[UnitedToolProvider] Disabled tool: {tool_name}")
    
    async def reload_tools(self):
        """Reload all tools"""
        logger.info("[UnitedToolProvider] Reloading all tools...")
        self.all_tools.clear()
        self._initialized = False
        await self.initialize()
    
    # Compatibility methods - maintain compatibility with existing code
    def get_legacy_tool_registry(self):
        """Get Python tool registry (compatibility method)"""
        return self.legacy_provider.registry
    
    def get_mcp_server_manager(self):
        """Get MCP server manager (compatibility method)"""
        return self.mcp_provider.mcp_manager
    
    async def execute_legacy_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute Legacy tool (compatibility method)"""
        return await self.legacy_provider.execute_tool(tool_name, **kwargs)
    
    def get_legacy_tool_specs(self, tool_names: Optional[List[str]] = None) -> List[Dict]:
        """Get Legacy tool specifications for function calling
        
        Args:
            tool_names: Optional list of tool names to get specs for
            
        Returns:
            List of Bedrock tool specifications
        """
        specs = []
        
        for tool_name, tool_info in self.all_tools.items():
            if tool_names and tool_name not in tool_names:
                continue
            
            if not tool_info.enabled:
                continue
            
            # Only Python tools have Bedrock specs
            if tool_info.type == ToolType.LEGACY and tool_info.config:
                tool_spec = tool_info.config.get("tool_spec")
                if tool_spec:
                    specs.append(tool_spec)
        
        return specs


# Create singleton instance
tool_provider = ToolProvider()
