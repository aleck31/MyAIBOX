"""
MCP server management and configuration
"""
from typing import Dict, List, Optional, Any
from decimal import Decimal
from botocore.exceptions import ClientError
from core.config import env_config
from core.logger import logger
from utils.aws import get_aws_resource


class MCPServerManager:
    """Manager for MCP servers and configuration"""
    
    def __init__(self):
        try:
            self.dynamodb = get_aws_resource('dynamodb')
            self.table_name = env_config.database_config['setting_table']
            self.table = self.dynamodb.Table(self.table_name)
            logger.debug(f"Initialized MCPServerManager with table: {self.table_name}")
            # Cache for MCP server configurations
            self._mcp_servers_cache = None
        except Exception as e:
            logger.error(f"Failed to initialize MCPServerManager: {str(e)}")
            raise

    def _decimal_to_numeric(self, obj):
        """Helper function to convert Decimal values to appropriate numeric types in nested structures"""
        if isinstance(obj, dict):
            return {key: self._decimal_to_numeric(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._decimal_to_numeric(item) for item in obj]
        elif isinstance(obj, Decimal):
            # Convert to float first
            float_val = float(obj)
            # If the float is equivalent to an integer (no decimal part), convert to int
            if float_val.is_integer():
                return int(float_val)
            return float_val
        return obj

    def _numeric_to_decimal(self, obj):
        """Helper function to convert numeric values to Decimal for DynamoDB storage"""
        if isinstance(obj, dict):
            return {key: self._numeric_to_decimal(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._numeric_to_decimal(item) for item in obj]
        elif isinstance(obj, (float, int)) and not isinstance(obj, bool):
            return Decimal(str(obj))
        return obj

    def flush_cache(self):
        """Force flush MCP servers cache"""
        logger.debug("Flushing MCP servers cache")
        self._mcp_servers_cache = None

    def _load_mcp_servers_from_db(self) -> Dict[str, Any]:
        """Load MCP server configurations from database and update cache"""
        try:
            # Get MCP server configurations from DynamoDB
            response = self.table.get_item(
                Key={
                    'setting_name': 'mcp_servers',
                    'type': 'global'
                }
            )
            
            if 'Item' not in response:
                logger.warning("No MCP server configurations found in database")
                return {}

            # Convert stored data and update cache
            servers_data = self._decimal_to_numeric(response['Item'].get('servers', {}))
            # Ensure we're returning a Dict[str, Any] as specified in the return type
            if not isinstance(servers_data, dict):
                servers_data = {}
            self._mcp_servers_cache = servers_data
            return servers_data
        except Exception as e:
            logger.error(f"Error loading MCP server configurations from database: {str(e)}")
            return {}


    def _save_servers_to_db(self, servers: Dict) -> None:
        """Save MCP server configurations to database and flush cache
        
        Args:
            servers: Dictionary of server configurations
        """
        self.table.put_item(
            Item={
                'setting_name': 'mcp_servers',
                'type': 'global',
                'servers': self._numeric_to_decimal(servers)
            }
        )
        self.flush_cache()

    def get_mcp_servers(self) -> Dict:
        """Get all MCP server configurations
        
        Returns:
            Dict: Dictionary of MCP server configurations
        """
        try:
            # Get MCP servers from cache or load from database
            if self._mcp_servers_cache is None:
                return self._load_mcp_servers_from_db()
            else:
                return self._mcp_servers_cache
        except Exception as e:
            logger.error(f"Error getting MCP server configurations: {str(e)}")
            return {}

    def get_mcp_server(self, mcp_server: str) -> Optional[Dict]:
        """Get configuration for a specific MCP server
        
        Args:
            mcp_server: Name of the MCP server
            
        Returns:
            Dict: MCP server configuration or None if not found
        """
        try:
            servers = self.get_mcp_servers()
            if mcp_server in servers:
                return servers[mcp_server]
            else:
                logger.warning(f"MCP server not found: {mcp_server}")
                return None
        except Exception as e:
            logger.error(f"Error getting MCP server configuration: {str(e)}")
            return None

    def validate_mcp_server_config(self, server_config: Dict) -> bool:
        """Validate MCP server configuration
        
        Args:
            server_config: Server configuration to validate
            
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(server_config, dict):
            raise ValueError("Server configuration must be a dictionary")
        
        # Get server type (default to 'http' for backward compatibility)
        server_type = server_config.get('type', 'http')
        
        if server_type not in ['stdio', 'http', 'sse']:
            raise ValueError(f"Unsupported server type: {server_type}")
        
        # Validate based on server type
        if server_type == 'stdio':
            if 'command' not in server_config:
                raise ValueError("stdio server requires 'command' field")
            if not isinstance(server_config.get('args', []), list):
                raise ValueError("stdio server 'args' must be a list")
            if 'env' in server_config and not isinstance(server_config['env'], dict):
                raise ValueError("stdio server 'env' must be a dictionary")
                
        elif server_type in ['http', 'sse']:
            if 'url' not in server_config:
                raise ValueError(f"{server_type} server requires 'url' field")
            url = server_config['url']
            if not isinstance(url, str) or not (url.startswith('http://') or url.startswith('https://')):
                raise ValueError(f"{server_type} server 'url' must be a valid HTTP/HTTPS URL")
        
        return True

    def get_mcp_server_type(self, server_config: Dict) -> str:
        """Get MCP server type from configuration
        
        Args:
            server_config: Server configuration
            
        Returns:
            str: Server type ('stdio', 'http', or 'sse')
        """
        # Explicit type field takes precedence
        if 'type' in server_config:
            return server_config['type']
        
        # Backward compatibility: infer type from configuration
        if 'command' in server_config:
            return 'stdio'
        elif 'url' in server_config:
            return 'http'  # Default HTTP for URL-based servers
        else:
            return 'http'  # Default fallback

    def add_mcp_server(self, mcp_server: str, server_config: Dict) -> bool:
        """Add a new MCP server configuration
        
        Args:
            mcp_server: Name of the MCP server
            server_config: Configuration for the MCP server
            
        Returns:
            bool: True if successful
        """
        try:
            # Validate configuration
            self.validate_mcp_server_config(server_config)
            
            # Get current MCP server configurations
            servers = self.get_mcp_servers()
            
            # Check if server with same name exists
            if mcp_server in servers:
                raise ValueError(f"MCP server with name '{mcp_server}' already exists")
            
            # Add new server configuration
            servers[mcp_server] = server_config
            
            # Save to database
            self._save_servers_to_db(servers)
            
            server_type = self.get_mcp_server_type(server_config)
            logger.info(f"Added new MCP server: {mcp_server} (type: {server_type})")
            return True
        except Exception as e:
            logger.error(f"Error adding MCP server: {str(e)}")
            raise

    def update_mcp_server(self, mcp_server: str, server_config: Dict) -> bool:
        """Update an existing MCP server configuration
        
        Args:
            mcp_server: Name of the MCP server
            server_config: Updated configuration for the MCP server
            
        Returns:
            bool: True if successful
        """
        try:
            # Validate configuration
            self.validate_mcp_server_config(server_config)
            
            # Get current MCP server configurations
            servers = self.get_mcp_servers()
            
            # Update server configuration (create if not exists)
            servers[mcp_server] = server_config
            
            # Save to database
            self._save_servers_to_db(servers)
            
            server_type = self.get_mcp_server_type(server_config)
            logger.info(f"Updated MCP server: {mcp_server} (type: {server_type})")
            return True
        except Exception as e:
            logger.error(f"Error updating MCP server: {str(e)}")
            raise

    def delete_mcp_server(self, mcp_server: str) -> bool:
        """Delete an MCP server configuration
        
        Args:
            mcp_server: Name of the MCP server to delete
            
        Returns:
            bool: True if successful
        """
        try:
            # Get current MCP server configurations
            servers = self.get_mcp_servers()
            
            # Check if server exists
            if mcp_server not in servers:
                raise ValueError(f"MCP server with name '{mcp_server}' not found")
            
            # Delete server configuration
            del servers[mcp_server]
            
            # Save to database
            self._save_servers_to_db(servers)
            
            logger.info(f"Deleted MCP server: {mcp_server}")
            return True
        except Exception as e:
            logger.error(f"Error deleting MCP server: {str(e)}")
            raise

    def init_default_mcp_servers(self) -> bool:
        """Initialize default MCP server configurations if none exist
        
        Returns:
            bool: True if successful
        """
        try:
            servers = self.get_mcp_servers()
            if not servers:
                default_servers = {
                    "exa-server": {
                        "type": "http",
                        "url": "https://mcp.exa.ai/mcp?apiKey=8a72edef-4f2a-4bc8-ad59-d2b47384efca",
                        "disabled": False
                    },
                    "core-mcp-server": {
                        "type": "stdio",
                        "command": "uvx",
                        "args": ["awslabs.core-mcp-server@latest"],
                        "env": {
                            "FASTMCP_LOG_LEVEL": "ERROR"
                        },
                        "disabled": True
                    },
                    "awslabs.nova-canvas-mcp-server": {
                        "type": "stdio",
                        "command": "uvx",
                        "args": ["awslabs.nova-canvas-mcp-server@latest"],
                        "env": {
                            "AWS_PROFILE": "lab",
                            "AWS_REGION": "us-east-1",
                            "FASTMCP_LOG_LEVEL": "ERROR"
                        },
                        "disabled": False
                    },
                    "fastmcp-demo-sse": {
                        "type": "sse",
                        "url": "http://localhost:8000/sse",
                        "disabled": True,
                        "description": "Demo FastMCP SSE server - run 'fastmcp run server.py --transport sse' to start"
                    }
                }
                
                # Save to database
                self._save_servers_to_db(default_servers)
                logger.info("Initialized default MCP server configurations")
                return True
            return False
        except Exception as e:
            logger.error(f"Error initializing default MCP server configurations: {str(e)}")
            return False

    def list_servers_by_type(self, server_type: Optional[str] = None) -> Dict[str, Dict]:
        """List MCP servers filtered by type
        
        Args:
            server_type: Optional server type filter ('stdio', 'http', 'sse')
            
        Returns:
            Dict: Filtered server configurations
        """
        all_servers = self.get_mcp_servers()
        
        if server_type is None:
            return all_servers
        
        filtered_servers = {}
        for name, config in all_servers.items():
            if self.get_mcp_server_type(config) == server_type:
                filtered_servers[name] = config
        
        return filtered_servers

    def get_server_info(self, server_name: str) -> Optional[Dict]:
        """Get detailed information about a specific server
        
        Args:
            server_name: Name of the server
            
        Returns:
            Dict: Server information including type and status
        """
        server_config = self.get_mcp_server(server_name)
        if not server_config:
            return None
        
        server_type = self.get_mcp_server_type(server_config)
        
        info = {
            "name": server_name,
            "type": server_type,
            "disabled": server_config.get("disabled", False),
            "config": server_config
        }
        
        # Add type-specific information
        if server_type == "stdio":
            info["command"] = server_config.get("command")
            info["args"] = server_config.get("args", [])
            info["env"] = server_config.get("env", {})
        elif server_type in ["http", "sse"]:
            info["url"] = server_config.get("url")

        return info

    def dynamic_add_tools(self):
        # 动态添加 MCP 工具到现有 Agent 的工具注册表
        original_dynamic_tools = {}
        # if hasattr(self.agent, 'tool_registry') and hasattr(self.agent.tool_registry, 'dynamic_tools'):
        #     # 备份原有的动态工具
        #     original_dynamic_tools = self.agent.tool_registry.dynamic_tools.copy()
            
        #     # 添加 MCP 工具
        #     for mcp_tool in mcp_tools:
        #         tool_name = getattr(mcp_tool, 'tool_name', f'mcp_tool_{id(mcp_tool)}')
        #         self.agent.tool_registry.dynamic_tools[tool_name] = mcp_tool
            
        #     logger.info(f"动态添加了 {len(mcp_tools)} 个 MCP 工具")

# Create a singleton instance
mcp_server_manager = MCPServerManager()
