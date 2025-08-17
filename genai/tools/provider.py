"""
Simplified Tool Provider for MyAIBOX
Leverages Strands native mixed tool support for unified tool management
"""
from typing import Dict, List, Optional, Any, Tuple
from contextlib import ExitStack
from core.logger import logger


class ToolProvider:
    """Simplified unified tool provider leveraging Strands native capabilities"""
    
    def __init__(self):
        # Lazy loading to avoid circular imports
        self._legacy_registry = None
        self._mcp_server_manager = None
    
    @property
    def legacy_registry(self):
        """Lazy load legacy tool registry"""
        if self._legacy_registry is None:
            from genai.tools.legacy.tool_registry import legacy_tool_registry
            self._legacy_registry = legacy_tool_registry
        return self._legacy_registry
    
    @property
    def mcp_server_manager(self):
        """Lazy load MCP server manager"""
        if self._mcp_server_manager is None:
            from genai.tools.mcp.mcp_server_manager import mcp_server_manager
            self._mcp_server_manager = mcp_server_manager
        return self._mcp_server_manager
    
    def get_tools_and_contexts(self, tool_config: Dict) -> Tuple[List, List]:
        """Get all tools and required context managers
        
        Args:
            tool_config: Tool configuration dictionary
            
        Returns:
            Tuple of (tools_list, context_managers_list)
            
        Note:
            Leverages Strands native mixed tool support - simply returns a list
            of tools that can be directly passed to Agent(tools=tools_list)
        """
        if not tool_config.get('enabled', True):
            logger.debug("[ToolProvider] Tools disabled by configuration")
            return [], []
            
        tools = []
        context_managers = []
        
        # Load specific legacy tools
        legacy_tool_names = tool_config.get('legacy_tools', [])
        if legacy_tool_names:
            legacy_tools = self._get_specific_legacy_tools(legacy_tool_names)
            tools.extend(legacy_tools)
            logger.debug(f"[ToolProvider] Added {len(legacy_tools)} legacy tools")
        
        # Strands builtin tools
        if tool_config.get('strands_tools_enabled', True):
            strands_tools = self._get_strands_tools()
            tools.extend(strands_tools)
            logger.debug(f"[ToolProvider] Added {len(strands_tools)} Strands tools")
        
        # MCP tools (require context management)
        if tool_config.get('mcp_tools_enabled', False):
            mcp_clients = self._get_mcp_clients()
            context_managers.extend(mcp_clients)
            logger.debug(f"[ToolProvider] Added {len(mcp_clients)} MCP clients")
        
        logger.debug(f"[ToolProvider] Total: {len(tools)} direct tools, {len(context_managers)} MCP clients")
        return tools, context_managers

    def _get_specific_legacy_tools(self, tool_names: List[str]) -> List:
        """Get specific legacy tools by name
        
        Args:
            tool_names: List of specific tool names to load
            
        Returns:
            List of Strands-compatible tool functions
        """
        from strands import tool
        
        tools = []
        for tool_name in tool_names:
            if tool_name in self.legacy_registry.tools:
                # Convert to Strands tool using @tool decorator
                strands_tool = tool(self.legacy_registry.tools[tool_name])
                tools.append(strands_tool)
                logger.debug(f"[ToolProvider] Loaded legacy tool: {tool_name}")
            else:
                logger.warning(f"[ToolProvider] Legacy tool not found: {tool_name}")
        
        return tools
    
    def _get_strands_tools(self) -> List:
        """Get all Strands builtin tools"""
        try:
            from genai.tools.strands.builtin_tools import load_builtin_tools
            # Load all Strands tools by default
            return load_builtin_tools()
        except ImportError:
            logger.warning("[ToolProvider] Strands builtin tools not available")
            return []
    
    def _get_mcp_clients(self) -> List:
        """Get all enabled MCP clients"""
        
        clients = []
        servers = self.mcp_server_manager.get_mcp_servers()
        
        for server_name, server_config in servers.items():
            if server_config.get('disabled', False):
                logger.debug(f"[ToolProvider] Skipping disabled MCP server: {server_name}")
                continue
            
            try:
                client = self._create_mcp_client(server_config)
                if client:
                    clients.append(client)
                    logger.debug(f"[ToolProvider] Created MCP client: {server_name}")
            except Exception as e:
                logger.warning(f"[ToolProvider] Failed to create MCP client {server_name}: {e}")
        
        return clients
    
    def _create_mcp_client(self, server_config: Dict):
        """Create single MCP client based on server configuration"""
        from strands.tools.mcp import MCPClient
        
        server_type = self.mcp_server_manager.get_mcp_server_type(server_config)
        
        if server_type == 'stdio':
            from mcp import stdio_client, StdioServerParameters
            return MCPClient(lambda: stdio_client(
                StdioServerParameters(
                    command=server_config['command'],
                    args=server_config.get('args', []),
                    env=server_config.get('env', {})
                )
            ))
        elif server_type == 'http':
            from mcp.client.streamable_http import streamablehttp_client
            return MCPClient(lambda: streamablehttp_client(server_config['url']))
        elif server_type == 'sse':
            from mcp.client.sse import sse_client
            return MCPClient(lambda: sse_client(server_config['url']))
        else:
            logger.error(f"[ToolProvider] Unsupported MCP server type: {server_type}")
            return None
    
    def list_tools(self, enabled_only: bool = True) -> List[Dict]:
        """List available tools for UI/debugging purposes"""
        tools_info = []
        
        # Legacy tools
        for tool_name, tool_func in self.legacy_registry.tools.items():
            description = tool_func.__doc__ or f"Legacy tool: {tool_name}"
            tools_info.append({
                'name': tool_name,
                'type': 'legacy',
                'description': description.strip(),
                'enabled': True
            })
        
        # Strands tools
        try:
            from genai.tools.strands.builtin_tools import BUILTIN_TOOLS
            for tool_name in BUILTIN_TOOLS:
                tools_info.append({
                    'name': tool_name,
                    'type': 'strands',
                    'description': f"Strands builtin tool: {tool_name}",
                    'enabled': True
                })
        except ImportError:
            pass
        
        # MCP servers
        servers = self.mcp_server_manager.get_mcp_servers()
        for server_name, server_config in servers.items():
            tools_info.append({
                'name': server_name,
                'type': 'mcp_server',
                'description': f"MCP server: {server_name}",
                'enabled': not server_config.get('disabled', False)
            })
        
        if enabled_only:
            tools_info = [tool for tool in tools_info if tool['enabled']]
        
        return tools_info
    
    async def reload_tools(self):
        """Reload tools (legacy compatibility)"""
        logger.info("[ToolProvider] Reload tools called")
        # In simplified version, tools are loaded on-demand, so no action needed
        pass


# Create singleton instance
tool_provider = ToolProvider()
