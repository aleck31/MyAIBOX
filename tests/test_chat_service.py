#!/usr/bin/env python3
"""
Test script for ChatService after converting from async to sync
"""
import sys
import os
import asyncio
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.session import Session, SessionMetadata
from core.service.chat_service import ChatService
from common.logger import setup_logger, logger
from genai.models.model_manager import model_manager

async def test_chat_service():
    """Test ChatService functionality"""
    logger.info("🧪 Testing ChatService...")
    
    try:
        # Initialize model manager
        model_manager.init_default_models()
        
        # Create session
        session = Session(
            session_id="test_chat_session",
            session_name="Chat Test Session",
            created_time=datetime.now(),
            updated_time=datetime.now(),
            user_name="demo",
            metadata=SessionMetadata(module_name="Assistant"),
            history=[]
        )
        
        # Initialize service
        chat_service = ChatService(module_name="Assistant")
        
        # Test streaming chat
        logger.info("Testing streaming_reply...")
        response_count = 0
        
        async for chunk in chat_service.streaming_reply(
            session=session,
            message={"text": "Hello! Please respond with a simple greeting."},
            history=[]
        ):
            response_count += 1
            logger.info(f"📨 Chat chunk {response_count}: {chunk}")
            
            # Limit output for testing
            if response_count >= 5:
                break
        
        if response_count > 0:
            logger.info("✅ ChatService streaming_reply test PASSED")
            
            # Test session role methods
            logger.info("Testing session role methods...")
            
            # Get current role
            current_role = await chat_service.get_session_role(session)
            logger.info(f"Current role: {current_role}")
            
            # Update role
            await chat_service.update_session_role(session, "creative")
            updated_role = await chat_service.get_session_role(session)
            logger.info(f"Updated role: {updated_role}")
            
            # Clear history
            await chat_service.clear_history(session)
            logger.info("History cleared")
            
            logger.info("✅ ChatService ALL TESTS PASSED!")
            return True
        else:
            logger.error("❌ ChatService test FAILED - No response chunks")
            return False
            
    except Exception as e:
        logger.error(f"❌ ChatService test FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_chat_service())
    sys.exit(0 if success else 1)
