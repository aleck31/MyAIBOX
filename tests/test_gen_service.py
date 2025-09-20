#!/usr/bin/env python3
"""
Test script for GenService after converting from async to sync
"""
import sys
import os
import asyncio
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.session import Session, SessionMetadata
from core.service.gen_service import GenService
from common.logger import setup_logger, logger
from genai.models.model_manager import model_manager

async def test_gen_service():
    """Test GenService functionality"""
    logger.info("🧪 Testing GenService...")
    
    try:
        # Initialize model manager
        model_manager.init_default_models()
        
        # Create session
        session = Session(
            session_id="test_gen_session",
            session_name="Gen Test Session",
            created_time=datetime.now(),
            updated_time=datetime.now(),
            user_name="demo",
            metadata=SessionMetadata(module_name="Text"),
            history=[]
        )
        
        # Initialize service
        gen_service = GenService(module_name="Text")
        
        # Test 1: Stateless generation
        logger.info("Testing gen_text_stateless...")
        response = await gen_service.gen_text_stateless(
            content={"text": "Say 'Hello World' in exactly two words"}
        )
        
        if response:
            logger.info(f"📝 Stateless response: {response}")
            logger.info("✅ GenService gen_text_stateless test PASSED")
        else:
            logger.error("❌ GenService gen_text_stateless test FAILED")
            return False
        
        # Test 2: Session-based generation
        logger.info("Testing gen_text...")
        response = await gen_service.gen_text(
            session=session,
            content={"text": "Count from 1 to 3, one number per line"}
        )
        
        if response:
            logger.info(f"📝 Session response: {response}")
            logger.info("✅ GenService gen_text test PASSED")
        else:
            logger.error("❌ GenService gen_text test FAILED")
            return False
        
        # Test 3: Streaming generation
        logger.info("Testing gen_text_stream...")
        response_count = 0
        
        async for chunk in gen_service.gen_text_stream(
            session=session,
            content={"text": "List three colors: red, blue, green"}
        ):
            response_count += 1
            logger.info(f"📨 Stream chunk {response_count}: {chunk}")
            
            # Limit output for testing
            if response_count >= 5:
                break
        
        if response_count > 0:
            logger.info("✅ GenService gen_text_stream test PASSED")
            logger.info("✅ GenService ALL TESTS PASSED!")
            return True
        else:
            logger.error("❌ GenService gen_text_stream test FAILED")
            return False
            
    except Exception as e:
        logger.error(f"❌ GenService test FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_gen_service())
    sys.exit(0 if success else 1)
