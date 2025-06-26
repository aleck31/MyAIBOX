#!/usr/bin/env python3
"""
Test exa-server MCP connection
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from genai.tools.tool_provider import MCPToolProvider
from genai.tools.mcp.mcp_server_manager import mcp_server_manager


async def test_exa_server():
    """Test exa-server connection"""
    
    print("=== Testing exa-server MCP Connection ===\n")
    
    try:
        # Get exa-server configuration
        config = mcp_server_manager.get_mcp_tools('exa-server')
        if not config:
            print("✗ exa-server configuration not found")
            return
        
        print(f"Server config: {config}")
        print(f"Disabled: {config.get('disabled', False)}")
        print(f"URL: {config.get('url')}")
        
        if config.get('disabled', False):
            print("⚠️  Server is disabled, skipping connection test")
            return
        
        # Create MCP tool provider
        provider = MCPToolProvider()
        
        # Try to create MCP client
        print("\nTesting MCP client creation...")
        mcp_client = await provider._create_mcp_client('exa-server', config)
        
        if not mcp_client:
            print("✗ Failed to create MCP client")
            return
        
        print("✓ MCP client created successfully")
        
        # Try to list tools
        print("Testing tool listing...")
        try:
            with mcp_client:
                tools = mcp_client.list_tools_sync()
                print(f"✓ Successfully retrieved {len(tools)} tools from exa-server")
                
                # List the tools
                for i, tool in enumerate(tools):
                    print(f"  {i+1}. Tool object type: {type(tool)}")
                    print(f"      Available attributes: {dir(tool)}")
                    
                    # Try different ways to get tool name and description
                    tool_name = getattr(tool, 'name', None) or getattr(tool, 'tool_name', None) or 'unknown'
                    tool_desc = getattr(tool, 'description', None) or getattr(tool, 'desc', None) or 'No description'
                    
                    print(f"      Name: {tool_name}")
                    print(f"      Description: {tool_desc}")
                    print()
                
        except Exception as tool_error:
            print(f"✗ Error listing tools: {tool_error}")
            print(f"Error type: {type(tool_error).__name__}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_exa_server())
