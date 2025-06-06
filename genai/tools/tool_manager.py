"""
MCP tools management and configuration
"""
from typing import Dict, List, Optional
from decimal import Decimal
from botocore.exceptions import ClientError
from core.config import env_config
from core.logger import logger
from utils.aws import get_aws_resource


class ToolManager:
    """Manager for MCP servers and tools"""
    
    def __init__(self):
        try:
            self.dynamodb = get_aws_resource('dynamodb')
            self.table_name = env_config.database_config['setting_table']
            self.table = self.dynamodb.Table(self.table_name)
            logger.debug(f"Initialized ToolManager with table: {self.table_name}")
            # Cache for MCP server configurations
            self._mcp_servers_cache = None
        except Exception as e:
            logger.error(f"Failed to initialize ToolManager: {str(e)}")
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
        elif isinstance(obj, (float, int)):
            return Decimal(str(obj))
        return obj

    def flush_cache(self):
        """Force flush MCP servers cache"""
        logger.debug("Flushing MCP servers cache")
        self._mcp_servers_cache = None

    def _load_mcp_servers_from_db(self) -> Dict:
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
            self._mcp_servers_cache = servers_data
            return servers_data
        except Exception as e:
            logger.error(f"Error loading MCP server configurations from database: {str(e)}")
            return {}

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

    def get_mcp_tools(self, mcp_server: str) -> Optional[Dict]:
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

    def add_mcp_server(self, mcp_server: str, server_config: Dict) -> bool:
        """Add a new MCP server configuration
        
        Args:
            mcp_server: Name of the MCP server
            server_config: Configuration for the MCP server
            
        Returns:
            bool: True if successful
        """
        try:
            # Get current MCP server configurations
            servers = self.get_mcp_servers()
            
            # Check if server with same name exists
            if mcp_server in servers:
                raise ValueError(f"MCP server with name '{mcp_server}' already exists")
            
            # Add new server configuration
            servers[mcp_server] = server_config
            
            # Update table and invalidate cache
            self.table.put_item(
                Item={
                    'setting_name': 'mcp_servers',
                    'type': 'global',
                    'servers': self._numeric_to_decimal(servers)
                }
            )
            self.flush_cache()
            logger.info(f"Added new MCP server: {mcp_server}")
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
            # Get current MCP server configurations
            servers = self.get_mcp_servers()
            
            # Check if server exists
            if mcp_server not in servers:
                raise ValueError(f"MCP server with name '{mcp_server}' not found")
            
            # Update server configuration
            servers[mcp_server] = server_config
            
            # Update table and invalidate cache
            self.table.put_item(
                Item={
                    'setting_name': 'mcp_servers',
                    'type': 'global',
                    'servers': self._numeric_to_decimal(servers)
                }
            )
            self.flush_cache()
            logger.info(f"Updated MCP server: {mcp_server}")
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
            
            # Update table and invalidate cache
            self.table.put_item(
                Item={
                    'setting_name': 'mcp_servers',
                    'type': 'global',
                    'servers': self._numeric_to_decimal(servers)
                }
            )
            self.flush_cache()
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
                    "core-mcp-server": {
                        "command": "uvx",
                        "args": ["awslabs.core-mcp-server@latest"],
                        "disabled": True,
                        "env": {
                            "FASTMCP_LOG_LEVEL": "ERROR"
                        },
                        "autoApprove": []
                    },
                    "exa-server": {
                        "url": "https://mcp.exa.ai/mcp?apiKey=8a72edef-4f2a-4bc8-ad59-d2b47384efca",
                        "args": [],
                        "disabled": False
                    }
                }
                
                # Update table and invalidate cache
                self.table.put_item(
                    Item={
                        'setting_name': 'mcp_servers',
                        'type': 'global',
                        'servers': self._numeric_to_decimal(default_servers)
                    }
                )
                self.flush_cache()
                logger.info("Initialized default MCP server configurations")
                return True
            return False
        except Exception as e:
            logger.error(f"Error initializing default MCP server configurations: {str(e)}")
            return False


# Create a singleton instance
tool_manager = ToolManager()
