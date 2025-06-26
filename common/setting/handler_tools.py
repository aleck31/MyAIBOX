"""
Tool Management Handlers for Settings
"""
import json
import asyncio
from typing import Dict, List, Tuple, Any, Optional
import gradio as gr
from core.logger import logger
from genai.tools.mcp.mcp_server_manager import mcp_server_manager
from genai.tools.tool_provider import tool_provider, MCPToolProvider, ToolType


class ToolHandlers:
    """Handlers for tool management operations"""
    
    @staticmethod
    def refresh_mcp_servers_with_tools() -> Tuple[List[List], str]:
        """Refresh the list of MCP servers and get actual tool counts
        
        Returns:
            Tuple of (server_data, status_message)
        """
        try:
            # First try to initialize universal tool manager to get accurate tool counts
            try:                
                # Check if we're in an async context
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context, but this is a sync method
                    # We'll use the sync approach
                    logger.debug("[ToolHandlers] In async context, using sync tool count approach")
                except RuntimeError:
                    # No running loop, we can create one
                    logger.debug("[ToolHandlers] No async context, could create one if needed")
                
                # Try to get tool counts if universal tool manager is initialized
                if hasattr(tool_provider, '_initialized') and tool_provider._initialized:
                    logger.debug("[ToolHandlers] Universal tool manager is initialized")
                else:
                    logger.debug("[ToolHandlers] Universal tool manager not initialized")
                    
            except Exception as e:
                logger.debug(f"[ToolHandlers] Could not check universal tool manager: {str(e)}")
            
            # Get server configurations
            servers = mcp_server_manager.get_mcp_servers()
            server_data = []
            
            for server_name, config in servers.items():
                status = "Disabled" if config.get('disabled', False) else "Enabled"
                server_type = config.get('type', 'unknown')
                
                # Build URL/Command display based on server type
                if server_type == 'stdio':
                    command = config.get('command', 'N/A')
                    args = config.get('args', [])
                    if args:
                        # Format args nicely
                        args_str = ' '.join(f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in args)
                        url_display = f"{command} {args_str}"
                    else:
                        url_display = command
                elif server_type == 'http':
                    url_display = config.get('url', 'N/A')
                elif server_type == 'sse':
                    url_display = config.get('url', 'N/A')
                else:
                    url_display = config.get('url', config.get('command', 'N/A'))
                
                # Get actual tool count
                tools_count = 0
                if not config.get('disabled', False):
                    tools_count = ToolHandlers._get_server_tool_count(server_name)
                
                server_data.append([
                    server_name,
                    server_type,
                    status,
                    url_display,
                    tools_count
                ])
            
            logger.info(f"[ToolHandlers] Refreshed {len(server_data)} MCP servers with tool counts")
            return server_data, f"✓ Loaded {len(server_data)} MCP servers"
            
        except Exception as e:
            logger.error(f"[ToolHandlers] Error refreshing MCP servers: {str(e)}")
            return [], f"✗ Error loading MCP servers: {str(e)}"
    
    @staticmethod
    def _get_server_tool_count(server_name: str) -> int:
        """Get the actual tool count for a specific server
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            Number of tools provided by the server
        """
        try:
            from genai.tools.tool_provider import tool_provider, ToolType
            
            # Try to initialize if not already done
            if not (hasattr(tool_provider, '_initialized') and tool_provider._initialized):
                logger.debug(f"[ToolHandlers] Initializing universal tool manager to get tool count for {server_name}")
                try:
                    # Use asyncio to run the async initialization
                    import asyncio
                    
                    # Check if we're in an async context
                    try:
                        loop = asyncio.get_running_loop()
                        # We're in an async context, but this is a sync method
                        # We can't await here, so we'll skip initialization
                        logger.debug(f"[ToolHandlers] In async context, cannot initialize universal tool manager synchronously")
                        return 0
                    except RuntimeError:
                        # No running loop, we can create one
                        logger.debug(f"[ToolHandlers] Creating new event loop to initialize universal tool manager")
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(tool_provider.initialize())
                            logger.debug(f"[ToolHandlers] Successfully initialized universal tool manager")
                        finally:
                            loop.close()
                            asyncio.set_event_loop(None)
                            
                except Exception as init_error:
                    logger.warning(f"[ToolHandlers] Failed to initialize universal tool manager: {str(init_error)}")
                    return 0
            
            if hasattr(tool_provider, '_initialized') and tool_provider._initialized:
                mcp_tools = tool_provider.list_tools(ToolType.MCP)
                count = len([t for t in mcp_tools if t.name.startswith(f"{server_name}:")])
                logger.debug(f"[ToolHandlers] Found {count} tools for {server_name}")
                return count
            else:
                logger.debug(f"[ToolHandlers] Universal tool manager still not initialized after attempt")
                return 0
                
        except Exception as e:
            logger.warning(f"[ToolHandlers] Error getting tool count for {server_name}: {str(e)}")
            return 0
    
    @staticmethod
    def get_server_details(servers_data: List[List], evt: gr.SelectData) -> Tuple[str, str, str, str, str, str]:
        """Get details for selected server
        
        Args:
            servers_data: Current server data (can be DataFrame or list)
            evt: Selection event data
            
        Returns:
            Tuple of server details
        """
        try:
            logger.info(f"[ToolHandlers] Selection event: row={evt.index[0]}")
            
            # Handle both DataFrame and list formats
            if servers_data is None:
                logger.warning(f"[ToolHandlers] No server data available")
                return "", "", "", "", "", "✗ No data available"
            
            # Convert DataFrame to list if needed
            if hasattr(servers_data, 'values'):
                # It's a DataFrame
                if servers_data.empty:
                    logger.warning(f"[ToolHandlers] Server data is empty")
                    return "", "", "", "", "", "✗ No servers available"
                servers_list = servers_data.values.tolist()
            else:
                # It's already a list
                if not servers_data:
                    logger.warning(f"[ToolHandlers] Server list is empty")
                    return "", "", "", "", "", "✗ No servers available"
                servers_list = servers_data
            
            if evt.index[0] >= len(servers_list):
                logger.warning(f"[ToolHandlers] Invalid selection: index={evt.index[0]}, data_length={len(servers_list)}")
                return "", "", "", "", "", "✗ Invalid selection"
            
            row = servers_list[evt.index[0]]
            server_name = row[0]
            server_type = row[1]
            status = row[2]
            url = row[3]
            
            logger.info(f"[ToolHandlers] Selected server: {server_name}")
            
            # Get full server config
            config = mcp_server_manager.get_mcp_tools(server_name)
            if config:
                full_url = config.get('url', config.get('command', 'N/A'))
                args = config.get('args', [])
                if args and server_type == 'stdio':
                    full_url = f"Command: {config.get('command', 'N/A')}, Args: {args}"
            else:
                full_url = 'Configuration not found'
            
            return (
                server_name,  # selected_server (hidden)
                server_name,  # server_name_display
                server_type,  # server_type_display
                full_url,     # server_url_display
                status,       # server_status_display
                f"✓ Selected server: {server_name}"  # status_message
            )
            
        except Exception as e:
            logger.error(f"[ToolHandlers] Error getting server details: {str(e)}")
            return "", "", "", "", "", f"✗ Error: {str(e)}"
    
    @staticmethod
    def _reload_tools_background(operation_name: str):
        """Reload tool provider in background thread
        
        Args:
            operation_name: Operation name for logging
        """
        def reload_task():
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Reload tool provider
                    from genai.tools.tool_provider import tool_provider
                    loop.run_until_complete(tool_provider.reload_tools())
                    logger.info(f"[ToolHandlers] Tools reloaded successfully after {operation_name}")
                except Exception as e:
                    logger.error(f"[ToolHandlers] Failed to reload tools after {operation_name}: {str(e)}")
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)
            except Exception as e:
                logger.error(f"[ToolHandlers] Error in background tool reload: {str(e)}")
        
        # Execute reload in background thread
        import threading
        threading.Thread(target=reload_task, daemon=True).start()

    @staticmethod
    def enable_server(server_name: str) -> Tuple[List[List], str]:
        """Enable an MCP server and reload tools
        
        Args:
            server_name: Name of the server to enable
            
        Returns:
            Tuple of (updated_server_data, status_message)
        """
        try:
            if not server_name:
                return [], "✗ No server selected"
            
            config = mcp_server_manager.get_mcp_tools(server_name)
            if not config:
                return [], f"✗ Server '{server_name}' not found"
            
            config['disabled'] = False
            success = mcp_server_manager.update_mcp_server(server_name, config)
            
            if success:
                # Async reload tools (non-blocking UI)
                ToolHandlers._reload_tools_background(f"enabling server '{server_name}'")
                
                # Return updated server list immediately
                server_data, _ = ToolHandlers.refresh_mcp_servers_with_tools()
                return server_data, f"✓ Enabled server '{server_name}' (tools reloading...)"
            else:
                return [], f"✗ Failed to enable server '{server_name}'"
                
        except Exception as e:
            logger.error(f"[ToolHandlers] Error enabling server: {str(e)}")
            return [], f"✗ Error enabling server: {str(e)}"
    
    @staticmethod
    def disable_server(server_name: str) -> Tuple[List[List], str]:
        """Disable an MCP server and reload tools
        
        Args:
            server_name: Name of the server to disable
            
        Returns:
            Tuple of (updated_server_data, status_message)
        """
        try:
            if not server_name:
                return [], "✗ No server selected"
            
            config = mcp_server_manager.get_mcp_tools(server_name)
            if not config:
                return [], f"✗ Server '{server_name}' not found"
            
            config['disabled'] = True
            success = mcp_server_manager.update_mcp_server(server_name, config)
            
            if success:
                # Async reload tools (non-blocking UI)
                ToolHandlers._reload_tools_background(f"disabling server '{server_name}'")
                
                # Return updated server list immediately
                server_data, _ = ToolHandlers.refresh_mcp_servers_with_tools()
                return server_data, f"✓ Disabled server '{server_name}' (tools reloading...)"
            else:
                return [], f"✗ Failed to disable server '{server_name}'"
                
        except Exception as e:
            logger.error(f"[ToolHandlers] Error disabling server: {str(e)}")
    @staticmethod
    def add_mcp_server(server_name: str, server_type: str, url_or_command: str, args: List[str] = None) -> Tuple[List[List], str]:
        """Add a new MCP server and reload tools
        
        Args:
            server_name: Name of the server
            server_type: Type of server (http, stdio, sse)
            url_or_command: URL for http/sse servers or command for stdio servers
            args: Arguments for stdio servers
            
        Returns:
            Tuple of (updated_server_data, status_message)
        """
        try:
            if not server_name or not server_type or not url_or_command:
                return [], "✗ Missing required fields"
            
            # Check if server already exists
            existing_config = mcp_server_manager.get_mcp_tools(server_name)
            if existing_config:
                return [], f"✗ Server '{server_name}' already exists"
            
            # Build server configuration
            config = {
                'type': server_type,
                'disabled': False
            }
            
            if server_type == 'stdio':
                config['command'] = url_or_command
                if args:
                    config['args'] = args
            else:  # http or sse
                config['url'] = url_or_command
            
            # Add server to database
            success = mcp_server_manager.add_mcp_server(server_name, config)
            
            if success:
                # Async reload tools (non-blocking UI)
                ToolHandlers._reload_tools_background(f"adding server '{server_name}'")
                
                # Return updated server list immediately
                server_data, _ = ToolHandlers.refresh_mcp_servers_with_tools()
                return server_data, f"✓ Added server '{server_name}' (tools reloading...)"
            else:
                return [], f"✗ Failed to add server '{server_name}'"
                
        except Exception as e:
            logger.error(f"[ToolHandlers] Error adding server: {str(e)}")
            return [], f"✗ Error adding server: {str(e)}"
    
    @staticmethod
    def delete_mcp_server(server_name: str) -> Tuple[List[List], str]:
        """Delete an MCP server and reload tools
        
        Args:
            server_name: Name of the server to delete
            
        Returns:
            Tuple of (updated_server_data, status_message)
        """
        try:
            if not server_name:
                return [], "✗ No server selected"
            
            # Check if server exists
            config = mcp_server_manager.get_mcp_tools(server_name)
            if not config:
                return [], f"✗ Server '{server_name}' not found"
            
            # Delete server from database
            success = mcp_server_manager.delete_mcp_server(server_name)
            
            if success:
                # Async reload tools (non-blocking UI)
                ToolHandlers._reload_tools_background(f"deleting server '{server_name}'")
                
                # Return updated server list immediately
                server_data, _ = ToolHandlers.refresh_mcp_servers_with_tools()
                return server_data, f"✓ Deleted server '{server_name}' (tools reloading...)"
            else:
                return [], f"✗ Failed to delete server '{server_name}'"
                
        except Exception as e:
            logger.error(f"[ToolHandlers] Error deleting server: {str(e)}")
            return [], f"✗ Error deleting server: {str(e)}"
    
    @staticmethod
    def test_server_connection(server_name: str) -> Tuple[Dict, str]:
        """Test connection to an MCP server
        
        Args:
            server_name: Name of the server to test
            
        Returns:
            Tuple of (test_results, status_message)
        """
        try:
            if not server_name:
                return {}, "✗ No server selected"
            
            config = mcp_server_manager.get_mcp_tools(server_name)
            if not config:
                return {}, f"✗ Server '{server_name}' not found"
            
            # Create a temporary MCP tool provider for testing
            provider = MCPToolProvider()
            
            # This would need to be async in a real implementation
            # For now, return a placeholder
            test_results = {
                "server_name": server_name,
                "server_type": config.get('type', 'unknown'),
                "server_url": config.get('url', 'N/A'),
                "status": "Connection test not implemented yet",
                "tools_found": 0,
                "error": None
            }
            
            return test_results, f"Connection test initiated for '{server_name}'"
            
        except Exception as e:
            logger.error(f"[ToolHandlers] Error testing server connection: {str(e)}")
            return {"error": str(e)}, f"✗ Error testing connection: {str(e)}"
    
    @staticmethod
    def add_mcp_server(name: str, server_type: str, url: str, args: str) -> Tuple[List[List], str]:
        """Add a new MCP server
        
        Args:
            name: Server name
            server_type: Type of server (http, stdio, sse)
            url: Server URL (for http/sse)
            args: Arguments (for stdio)
            
        Returns:
            Tuple of (updated_server_data, status_message)
        """
        try:
            if not name:
                return [], "✗ Server name is required"
            
            if not server_type:
                return [], "✗ Server type is required"
            
            # Validate inputs based on server type
            if server_type in ['http', 'sse'] and not url:
                return [], f"✗ URL is required for {server_type} servers"
            
            if server_type == 'stdio' and not args:
                return [], "✗ Arguments are required for stdio servers"
            
            # Check if server already exists
            existing_servers = mcp_server_manager.get_mcp_servers()
            if name in existing_servers:
                return [], f"✗ Server '{name}' already exists"
            
            # Build server config
            config = {
                'type': server_type,
                'disabled': False
            }
            
            if server_type in ['http', 'sse']:
                config['url'] = url
                config['args'] = []
            elif server_type == 'stdio':
                try:
                    parsed_args = json.loads(args) if args else []
                    config['args'] = parsed_args
                except json.JSONDecodeError:
                    return [], "✗ Invalid JSON format for arguments"
            
            # Add the server
            success = mcp_server_manager.update_mcp_server(name, config)
            
            if success:
                # Refresh server list
                server_data, _ = ToolHandlers.refresh_mcp_servers()
                return server_data, f"✓ Added server '{name}'"
            else:
                return [], f"✗ Failed to add server '{name}'"
                
        except Exception as e:
            logger.error(f"[ToolHandlers] Error adding MCP server: {str(e)}")
            return [], f"✗ Error adding server: {str(e)}"
    
    @staticmethod
    def get_server_tools(server_name: str) -> Tuple[List[List], str]:
        """Get tools for a specific server
        
        Args:
            server_name: Name of the server
            
        Returns:
            Tuple of (tools_data, status_message)
        """
        try:
            if not server_name:
                return [], "No server selected"
            
            tools_data = []
            
            # Try to get tools from universal tool manager
            try:
                from genai.tools.tool_provider import tool_provider
                if hasattr(tool_provider, '_initialized') and tool_provider._initialized:
                    mcp_tools = tool_provider.list_tools(ToolType.MCP)
                    
                    for tool_info in mcp_tools:
                        if tool_info.name.startswith(f"{server_name}:"):
                            # Extract tool name without server prefix
                            tool_name = tool_info.name.split(":", 1)[1]
                            description = tool_info.description or "No description available"
                            
                            tools_data.append([
                                tool_name,
                                description,
                                server_name
                            ])
                    
                    if tools_data:
                        return tools_data, f"✓ Loaded {len(tools_data)} tools for '{server_name}'"
                    else:
                        return [], f"No tools found for '{server_name}' (server may be disabled or not connected)"
                else:
                    return [], f"Tool manager not initialized - try refreshing the page"
                    
            except Exception as e:
                logger.warning(f"[ToolHandlers] Could not get tools from universal tool manager: {str(e)}")
                # Fallback to placeholder
                return [[f"example_tool", "Tool information not available", server_name]], f"Could not load tools for '{server_name}'"
            
        except Exception as e:
            logger.error(f"[ToolHandlers] Error getting server tools: {str(e)}")
            return [], f"✗ Error loading tools: {str(e)}"
