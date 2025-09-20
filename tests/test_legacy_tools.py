#!/usr/bin/env python3
"""
Test script to verify tool execution works correctly
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_legacy_tool_execution():
    """Test legacy tool execution directly"""
    print("Testing legacy tool execution...")
    
    try:
        from genai.tools.legacy.tool_registry import legacy_tool_registry
        
        # Test search_internet tool
        print("Testing search_internet tool...")
        result = await legacy_tool_registry.execute_tool(
            'search_internet',
            query='AWS regions Asia Pacific'
        )
        result_str = str(result)
        print(f"search_internet result: {result_str[:200]}..." if len(result_str) > 200 else f"search_internet result: {result}")
        
        # Test search_wikipedia tool
        print("\nTesting search_wikipedia tool...")
        result = await legacy_tool_registry.execute_tool(
            'search_wikipedia',
            query='Amazon Web Services'
        )
        result_str = str(result)
        print(f"search_wikipedia result: {result_str[:200]}..." if len(result_str) > 200 else f"search_wikipedia result: {result}")
        
        # Test get_weather tool
        print("\nTesting get_weather tool...")
        result = await legacy_tool_registry.execute_tool(
            'get_weather',
            place='Singapore'
        )
        result_str = str(result)
        print(f"get_weather result: {result_str[:200]}..." if len(result_str) > 200 else f"get_weather result: {result}")
        
    except Exception as e:
        print(f"Error testing legacy tools: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== Tool Execution Test ===")
    
    # Test async tool execution
    asyncio.run(test_legacy_tool_execution())
    
    print("\n=== Test Complete ===")
