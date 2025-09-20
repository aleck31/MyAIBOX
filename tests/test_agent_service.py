#!/usr/bin/env python3
"""
Test script for AgentService after converting from async to sync
"""
import sys
import os
import asyncio
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.session import Session, SessionMetadata
from core.service.agent_service import AgentService
from common.logger import setup_logger, logger
from genai.models.model_manager import model_manager

async def test_agent_service():
    """Test AgentService functionality"""
    logger.info("🧪 Testing AgentService...")
    
    try:
        # Initialize model manager
        model_manager.init_default_models()
        
        # Create session
        session = Session(
            session_id="test_agent_session",
            session_name="Agent Test Session",
            created_time=datetime.now(),
            updated_time=datetime.now(),
            user_name="demo",
            metadata=SessionMetadata(module_name="DeepSearch"),
            history=[]
        )
        
        # Initialize service
        agent_service = AgentService(module_name="DeepSearch")
        
        # Test 1: Streaming with history (AgentProvider is async)
        logger.info("Testing streaming_reply_with_history...")
        response_count = 0
        
        async for chunk in agent_service.streaming_reply_with_history(
            session=session,
            prompt="What is 2 + 2? Please explain briefly.",
            system_prompt="You are a helpful math assistant.",
            history=[]
        ):
            response_count += 1
            logger.info(f"📨 Agent chunk {response_count}: {chunk}")
            
            # Limit output for testing
            if response_count >= 5:
                break
        
        if response_count > 0:
            logger.info("✅ AgentService streaming_reply_with_history test PASSED")
        else:
            logger.error("❌ AgentService streaming_reply_with_history test FAILED")
            return False
        
        # Test 2: Single-turn streaming (AgentProvider is async)
        logger.info("Testing gen_text_stream...")
        response_count = 0
        
        async for chunk in agent_service.gen_text_stream(
            session=session,
            prompt="Name three programming languages",
            system_prompt="You are a programming expert."
        ):
            response_count += 1
            logger.info(f"📨 Single-turn chunk {response_count}: {chunk}")
            
            # Limit output for testing
            if response_count >= 5:
                break
        
        if response_count > 0:
            logger.info("✅ AgentService gen_text_stream test PASSED")
            
            # Test 3: Clear history
            await agent_service.clear_history(session)
            logger.info("✅ AgentService clear_history test PASSED")
            
            logger.info("✅ AgentService ALL TESTS PASSED!")
            return True
        else:
            logger.error("❌ AgentService gen_text_stream test FAILED")
            return False
            
    except Exception as e:
        logger.error(f"❌ AgentService test FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_agent_service())
    sys.exit(0 if success else 1)
