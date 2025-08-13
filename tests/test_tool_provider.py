#!/usr/bin/env python3
"""
Test suite for Universal Tool Manager integration
"""
import os
import sys
import asyncio
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from genai.tools.provider  import tool_provider, ToolType
from genai.agents.provider import AgentProvider
from core.session.models import Session, SessionMetadata
from core.service.service_factory import ServiceFactory


class TestUniversalToolManager:
    """Test cases for Universal Tool Manager"""
    
    @staticmethod
    async def test_initialization():
        """Test UniversalToolManager initialization"""
        print("=== Testing UniversalToolManager Initialization ===")
        
        try:
            await tool_provider.initialize()
            print("✓ UniversalToolManager initialized successfully")
            
            # Check tool counts
            legacy_tools = tool_provider.list_tools(ToolType.LEGACY)
            mcp_tools = tool_provider.list_tools(ToolType.MCP)
            
            print(f"✓ Loaded {len(legacy_tools)} Python tools")
            print(f"✓ Loaded {len(mcp_tools)} MCP tools")
            
            # List Python tools
            if legacy_tools:
                print("  Python tools:")
                for tool in legacy_tools:
                    print(f"    - {tool.name}: {tool.description[:50]}...")
            
            # List MCP tools
            if mcp_tools:
                print("  MCP tools:")
                for tool in mcp_tools:
                    print(f"    - {tool.name}: {tool.description[:50]}...")
            
            return True
            
        except Exception as e:
            print(f"✗ Initialization failed: {e}")
            return False
    
    @staticmethod
    async def test_strands_agent_integration():
        """Test Strands Agent integration with UniversalToolManager"""
        print("\n=== Testing Strands Agent Integration ===")
        
        try:
            # Create agent provider
            agent_provider = AgentProvider(
                model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
                system_prompt="You are a helpful assistant with access to various tools."
            )
            
            # Test getting available tools
            available_tools = await agent_provider.get_available_tools()
            print(f"✓ Available tools - Legacy(Python): {len(available_tools['legacy'])}, MCP: {len(available_tools['mcp'])}")
            
            # Test simple query with tools
            tool_config = {
                'enabled': True,
                'include_legacy': True,
                'include_mcp': False  # Disable MCP to avoid connection issues
            }
            
            test_prompt = "What tools do you have available? List them briefly."
            print(f"✓ Testing query: {test_prompt}")
            
            response_text = ""
            async for event in agent_provider.generate_stream(test_prompt, tool_config):
                if 'content' in event and 'text' in event['content']:
                    response_text += event['content']['text']
            
            if response_text:
                print(f"✓ Agent responded successfully ({len(response_text)} chars)")
                return True
            else:
                print("✗ No response received")
                return False
                
        except Exception as e:
            print(f"✗ Strands Agent integration failed: {e}")
            return False
    
    @staticmethod
    async def test_deepsearch_module():
        """Test deepsearch module functionality"""
        print("\n=== Testing DeepSearch Module ===")
        
        try:
            # Create agent service
            service = ServiceFactory.create_agent_service("deepsearch")
            print("✓ AgentService created")
            
            # Create test session
            session = Session(
                session_id="test-deepsearch-123",
                session_name="DeepSearch Test",
                created_time=datetime.now(),
                updated_time=datetime.now(),
                user_name="test-user",
                metadata=SessionMetadata(module_name="deepsearch")
            )
            print("✓ Test session created")
            
            # Test query
            test_query = "What is machine learning?"
            system_prompt = "You are a helpful AI assistant that provides clear and informative answers."
            
            print(f"✓ Testing query: {test_query}")
            
            response_parts = []
            async for chunk in service.gen_text_stream(session, test_query, system_prompt):
                if isinstance(chunk, dict) and 'text' in chunk:
                    response_parts.append(chunk['text'])
            
            full_response = ''.join(response_parts)
            if full_response:
                print(f"✓ DeepSearch query completed successfully ({len(full_response)} chars)")
                return True
            else:
                print("✗ No response received from DeepSearch")
                return False
                
        except Exception as e:
            print(f"✗ DeepSearch module test failed: {e}")
            return False
    
    @staticmethod
    async def run_all_tests():
        """Run all test cases"""
        print("🧪 Universal Tool Manager Test Suite")
        print("=" * 50)
        
        results = []
        
        # Test 1: Initialization
        results.append(await TestUniversalToolManager.test_initialization())
        
        # Test 2: Strands Agent Integration
        results.append(await TestUniversalToolManager.test_strands_agent_integration())
        
        # Test 3: DeepSearch Module
        results.append(await TestUniversalToolManager.test_deepsearch_module())
        
        # Summary
        passed = sum(results)
        total = len(results)
        
        print(f"\n{'=' * 50}")
        print(f"🏁 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! UniversalToolManager is working correctly.")
        else:
            print("⚠️  Some tests failed. Please check the output above.")
        
        return passed == total


async def main():
    """Main test runner"""
    success = await TestUniversalToolManager.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
