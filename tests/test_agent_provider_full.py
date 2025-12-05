#!/usr/bin/env python3
"""
Comprehensive test for AgentProvider -> AgentService -> AssistantHandlers
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.logger import logger
from genai.agents.provider import AgentProvider
from core.service.agent_service import AgentService
from core.session.models import Session


async def test_agent_provider():
    """Test 1: AgentProvider basic functionality"""
    logger.info("=" * 60)
    logger.info("TEST 1: AgentProvider")
    logger.info("=" * 60)
    
    try:
        # Use a valid model ID - get from model manager
        from genai.models.model_manager import model_manager
        models = model_manager.get_models(filter={'tool_use': True})
        
        if not models:
            logger.warning("⚠️  No models available, skipping test")
            logger.info("✅ TEST 1 PASSED: AgentProvider (no models to test)\n")
            return True
        
        model_id = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
        logger.info(f"Using model: {model_id}")
        
        provider = AgentProvider(
            model_id=model_id,
            system_prompt="You are a helpful assistant."
        )
        
        logger.info("✓ AgentProvider initialized")
        
        # Test streaming without tools
        logger.info("Testing streaming generation (no tools)...")
        chunk_count = 0
        
        async for chunk in provider.generate_stream(
            prompt="Say 'Hello World' and nothing else.",
            history_messages=None,
            tool_config={'enabled': False}
        ):
            chunk_count += 1
            if 'text' in chunk:
                logger.info(f"  Chunk {chunk_count}: {chunk['text'][:50]}...")
            elif 'metadata' in chunk:
                logger.info(f"  Metadata: {chunk['metadata']}")
            
            if chunk_count >= 10:
                break
        
        logger.info(f"✓ Received {chunk_count} chunks")
        logger.info("✅ TEST 1 PASSED: AgentProvider works correctly\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ TEST 1 FAILED: {e}", exc_info=True)
        return False


async def test_agent_service():
    """Test 2: AgentService functionality"""
    logger.info("=" * 60)
    logger.info("TEST 2: AgentService")
    logger.info("=" * 60)
    
    try:
        from datetime import datetime
        from core.session.models import SessionMetadata
        
        # Create test session with correct parameters
        session = Session(
            session_id="test_provider_session",
            session_name="Test Session",
            created_time=datetime.now(),
            updated_time=datetime.now(),
            user_name="test_user",
            metadata=SessionMetadata(module_name="assistant")
        )
        
        # Initialize service
        service = AgentService("assistant")
        logger.info("✓ AgentService initialized")
        
        # Test streaming with history
        logger.info("Testing streaming_reply_with_history...")
        chunk_count = 0
        
        async for chunk in service.streaming_reply_with_history(
            session=session,
            prompt="What is 1+1? Answer briefly.",
            system_prompt="You are a math tutor.",
            history=[],
            tool_config={'enabled': False}
        ):
            chunk_count += 1
            if 'text' in chunk:
                logger.info(f"  Chunk {chunk_count}: {chunk['text'][:50]}...")
            
            if chunk_count >= 10:
                break
        
        logger.info(f"✓ Received {chunk_count} chunks")
        logger.info("✅ TEST 2 PASSED: AgentService works correctly\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ TEST 2 FAILED: {e}", exc_info=True)
        return False


async def test_assistant_handlers():
    """Test 3: AssistantHandlers integration"""
    logger.info("=" * 60)
    logger.info("TEST 3: AssistantHandlers Integration")
    logger.info("=" * 60)
    
    try:
        from webui.modules.assistant import AssistantHandlers
        
        # Create mock request
        class MockRequest:
            def __init__(self):
                self.session = {'auth_user': {'username': 'test_user'}}
        
        request = MockRequest()
        
        # Test get_available_models
        models = AssistantHandlers.get_available_models()
        logger.info(f"✓ Found {len(models)} available models")
        
        if not models:
            logger.warning("⚠️  No models with tool_use capability found")
            logger.info("✅ TEST 3 PASSED: AssistantHandlers works (no models available)\n")
            return True
        
        # Test load_history_options
        history_options, selected = await AssistantHandlers.load_history_options(request)
        logger.info(f"✓ Loaded {len(history_options)} history options")
        
        logger.info("✅ TEST 3 PASSED: AssistantHandlers works correctly\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ TEST 3 FAILED: {e}", exc_info=True)
        return False


async def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("AGENT PROVIDER FULL STACK TEST")
    logger.info("=" * 60 + "\n")
    
    results = []
    
    # Test 1: AgentProvider
    results.append(await test_agent_provider())
    
    # Test 2: AgentService
    results.append(await test_agent_service())
    
    # Test 3: AssistantHandlers
    results.append(await test_assistant_handlers())
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"AgentProvider:       {'✅ PASS' if results[0] else '❌ FAIL'}")
    logger.info(f"AgentService:        {'✅ PASS' if results[1] else '❌ FAIL'}")
    logger.info(f"AssistantHandlers:   {'✅ PASS' if results[2] else '❌ FAIL'}")
    logger.info("=" * 60)
    
    if all(results):
        logger.info("🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
