#!/usr/bin/env python3
"""
Simple test for deepsearch module functionality
"""
import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.session.models import Session, SessionMetadata
from core.service.service_factory import ServiceFactory


async def test_deepsearch_simple():
    """Simple test of deepsearch functionality"""
    
    print("=== Simple DeepSearch Test ===\n")
    
    try:
        # Create agent service
        print("1. Creating AgentService...")
        service = ServiceFactory.create_agent_service("deepsearch")
        print("   ✓ AgentService created")
        
        # Create a simple session
        print("2. Creating test session...")
        session = Session(
            session_id="test-123",
            session_name="Test Session",
            created_time=datetime.now(),
            updated_time=datetime.now(),
            user_name="test-user",
            metadata=SessionMetadata(module_name="deepsearch")
        )
        print("   ✓ Test session created")
        
        # Test simple query
        print("3. Testing simple query...")
        test_query = "What is artificial intelligence?"
        system_prompt = "You are a helpful AI assistant that provides clear and concise answers."
        
        print(f"   Query: {test_query}")
        print("   Response: ", end="", flush=True)
        
        response_parts = []
        async for chunk in service.gen_text_stream(session, test_query, system_prompt):
            if isinstance(chunk, dict) and 'text' in chunk:
                text = chunk['text']
                print(text, end="", flush=True)
                response_parts.append(text)
        
        print("\n")
        
        full_response = ''.join(response_parts)
        if full_response:
            print("   ✓ Query completed successfully")
            print(f"   Response length: {len(full_response)} characters")
        else:
            print("   ⚠ Query completed but no response received")
            
    except Exception as e:
        print(f"   ✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Test Completed ===")


if __name__ == "__main__":
    asyncio.run(test_deepsearch_simple())
